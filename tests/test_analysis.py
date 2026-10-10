from fastapi.testclient import TestClient

from app.main import app


def test_annotate_variants():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t100\trs123\tA\tG\t150\tPASS\tAF=0.25
1\t200\trs456\tC\tT\t80\tPASS\tAF=0.10
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tGENE1\tPathogenic\trs123\t1\t100\t100\tA\tG
2\tsingle nucleotide variant\tVariant 2\t200\tGENE2\tBenign\trs456\t1\t200\t200\tC\tT
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Analysis Test Project",
                "description": "Project for variant annotation test",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "analysis_test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "analysis_test.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )

        assert annotation_response.status_code == 201

        response = client.post(
            f"/analysis/{vcf_id}/annotate",
        )

    assert response.status_code == 200

    data = response.json()

    assert data["vcf_id"] == vcf_id
    assert data["matched_variants"] == 2


def test_annotate_vcf_not_found():
    with TestClient(app) as client:
        response = client.post("/analysis/999999/annotate")

    assert response.status_code == 404
    assert response.json()["detail"] == "VCF file not found."


def test_annotate_without_annotation_file():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t150\tPASS\tAF=0.25
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "No Annotation Project",
                "description": "Project without annotation file",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "no_annotation.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        response = client.post(f"/analysis/{vcf_id}/annotate")

    assert response.status_code == 404
    assert response.json()["detail"] == ("Annotation file not found for this project.")


def test_annotate_unmatched_variant():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t150\tPASS\tAF=0.25
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tGENE1\tPathogenic\trs999\t2\t500\t500\tC\tT
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Unmatched Analysis Project",
                "description": "Project for unmatched annotation test",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "unmatched.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "unmatched.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )

        assert annotation_response.status_code == 201

        response = client.post(f"/analysis/{vcf_id}/annotate")

    assert response.status_code == 200
    assert response.json()["matched_variants"] == 0


def test_annotate_variants_twice():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t150\tPASS\tAF=0.25
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tGENE1\tPathogenic\trs123\t1\t100\t100\tA\tG
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Repeated Annotation Project",
                "description": "Test repeated variant annotation",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "repeated_annotation.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "repeated_annotation.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )

        assert annotation_response.status_code == 201

        first_response = client.post(f"/analysis/{vcf_id}/annotate")
        second_response = client.post(f"/analysis/{vcf_id}/annotate")

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.json()["matched_variants"] == 1
    assert second_response.json()["matched_variants"] == 1


def test_filter_variants():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs1\tA\tG\t150\tPASS\tAF=0.25
1\t200\trs2\tC\tT\t80\tPASS\tAF=0.10
2\t300\trs3\tG\tA\t20\tPASS\tAF=0.01
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tGENE1\tPathogenic\trs1\t1\t100\t100\tA\tG
2\tsingle nucleotide variant\tVariant 2\t200\tGENE2\tBenign\trs2\t1\t200\t200\tC\tT
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Variant Filtering Project",
                "description": "Test analysis variant filters",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "filter_test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )
        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "filter_test.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )
        assert annotation_response.status_code == 201

        annotate_response = client.post(f"/analysis/{vcf_id}/annotate")
        assert annotate_response.status_code == 200

        response = client.get(
            f"/analysis/{vcf_id}/variants",
            params={
                "min_quality": 50,
                "min_af": 0.05,
                "chrom": "1",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["variants"]) == 2

    assert data["variants"][0]["quality"] == 150.0
    assert data["variants"][0]["allele_frequency"] == 0.25
    assert data["variants"][0]["gene"] == "GENE1"
    assert data["variants"][0]["clinical_significance"] == "Pathogenic"

    assert data["variants"][1]["quality"] == 80.0
    assert data["variants"][1]["gene"] == "GENE2"
    assert data["variants"][1]["clinical_significance"] == "Benign"


def test_filter_variants_by_gene_and_significance():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs1\tA\tG\t150\tPASS\tAF=0.25
1\t200\trs2\tC\tT\t80\tPASS\tAF=0.10
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tBRCA1\tPathogenic\trs1\t1\t100\t100\tA\tG
2\tsingle nucleotide variant\tVariant 2\t200\tTP53\tBenign\trs2\t1\t200\t200\tC\tT
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Gene Filter Project",
                "description": "Test gene and significance filters",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "gene_filter.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )
        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "gene_filter.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )
        assert annotation_response.status_code == 201

        annotate_response = client.post(f"/analysis/{vcf_id}/annotate")
        assert annotate_response.status_code == 200

        response = client.get(
            f"/analysis/{vcf_id}/variants",
            params={
                "gene": "BRCA1",
                "significance": "Pathogenic",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert len(data["variants"]) == 1
    assert data["variants"][0]["gene"] == "BRCA1"
    assert data["variants"][0]["clinical_significance"] == "Pathogenic"
    assert data["variants"][0]["variant_id"] == "rs1"


def test_filter_variants_max_values_and_pagination():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs1\tA\tG\t20\tPASS\tAF=0.01
1\t200\trs2\tC\tT\t50\tPASS\tAF=0.05
1\t300\trs3\tG\tA\t100\tPASS\tAF=0.10
1\t400\trs4\tT\tC\t200\tPASS\tAF=0.50
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Pagination Filter Project",
                "description": "Test max filters and pagination",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "pagination_filter.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )
        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        response = client.get(
            f"/analysis/{vcf_id}/variants",
            params={
                "max_quality": 100,
                "max_af": 0.10,
                "limit": 1,
                "offset": 1,
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 1
    assert len(data["variants"]) == 1

    assert data["variants"][0]["variant_id"] == "rs2"
    assert data["variants"][0]["quality"] == 50.0
    assert data["variants"][0]["allele_frequency"] == 0.05


def test_filter_variants_vcf_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/analysis/999999/variants",
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "VCF file not found."


def test_filter_variants_invalid_pagination():
    with TestClient(app) as client:
        invalid_limit_response = client.get(
            "/analysis/1/variants",
            params={"limit": 0},
        )

        invalid_offset_response = client.get(
            "/analysis/1/variants",
            params={"offset": -1},
        )

    assert invalid_limit_response.status_code == 422
    assert invalid_offset_response.status_code == 422


def test_scientific_summary():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs1\tA\tG\t20\tPASS\tAF=0.005
1\t200\trs2\tC\tT\t50\tPASS\tAF=0.02
1\t300\trs3\tG\tA\t100\tPASS\tAF=0.07
2\t400\trs4\tT\tC\t200\tPASS\tAF=0.20
2\t500\trs5\tA\tC\t.\tPASS\tAF=0.60
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tBRCA1\tPathogenic\trs1\t1\t100\t100\tA\tG
2\tsingle nucleotide variant\tVariant 2\t100\tBRCA1\tPathogenic\trs2\t1\t200\t200\tC\tT
3\tsingle nucleotide variant\tVariant 3\t200\tTP53\tLikely_pathogenic\trs3\t1\t300\t300\tG\tA
4\tsingle nucleotide variant\tVariant 4\t300\tEGFR\tBenign\trs4\t2\t400\t400\tT\tC
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Scientific Summary Project",
                "description": "Test scientific summary statistics",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "summary_test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )
        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "summary_test.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )
        assert annotation_response.status_code == 201

        annotate_response = client.post(f"/analysis/{vcf_id}/annotate")
        assert annotate_response.status_code == 200

        response = client.get(f"/analysis/{vcf_id}/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["total_variants"] == 5

    assert data["quality_statistics"]["mean"] == 92.5
    assert data["quality_statistics"]["median"] == 75.0
    assert data["quality_statistics"]["min"] == 20.0
    assert data["quality_statistics"]["max"] == 200.0

    assert data["allele_frequency_distribution"] == {
        "0-0.01": 1,
        "0.01-0.05": 1,
        "0.05-0.1": 1,
        "0.1-0.5": 1,
        "0.5-1.0": 1,
    }

    assert data["top_genes"] == [
        {"gene": "BRCA1", "count": 2},
        {"gene": "EGFR", "count": 1},
        {"gene": "TP53", "count": 1},
    ]

    assert data["clinical_significance_counts"] == {
        "Pathogenic": 2,
        "Likely_pathogenic": 1,
        "Benign": 1,
    }


def test_scientific_summary_vcf_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/analysis/999999/summary",
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "VCF file not found."


def test_scientific_summary_without_quality_values():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs1\tA\tG\t.\tPASS\tAF=0.05
1\t200\trs2\tC\tT\t.\tPASS\tAF=0.10
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "No Quality Summary Project",
                "description": "Test summary without quality values",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "no_quality_summary.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        response = client.get(
            f"/analysis/{vcf_id}/summary",
        )

    assert response.status_code == 200

    data = response.json()

    assert data["total_variants"] == 2
    assert data["quality_statistics"] == {
        "mean": None,
        "median": None,
        "min": None,
        "max": None,
    }
    assert data["top_genes"] == []
    assert data["clinical_significance_counts"] == {}


def test_high_risk_variants():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs1\tA\tG\t150\tPASS\tAF=0.20
1\t200\trs2\tC\tT\t100\tPASS\tAF=0.10
1\t300\trs3\tG\tA\t200\tPASS\tAF=0.50
1\t400\trs4\tT\tC\t50\tPASS\tAF=0.30
1\t500\trs5\tA\tC\t300\tPASS\tAF=0.05
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tBRCA1\tPathogenic\trs1\t1\t100\t100\tA\tG
2\tsingle nucleotide variant\tVariant 2\t200\tTP53\tLikely_pathogenic\trs2\t1\t200\t200\tC\tT
3\tsingle nucleotide variant\tVariant 3\t300\tEGFR\tBenign\trs3\t1\t300\t300\tG\tA
4\tsingle nucleotide variant\tVariant 4\t400\tKRAS\tPathogenic\trs4\t1\t400\t400\tT\tC
5\tsingle nucleotide variant\tVariant 5\t500\tAPC\tPathogenic\trs5\t1\t500\t500\tA\tC
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "High Risk Project",
                "description": "Test high-risk variants",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "high_risk.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )
        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "high_risk.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )
        assert annotation_response.status_code == 201

        annotate_response = client.post(f"/analysis/{vcf_id}/annotate")
        assert annotate_response.status_code == 200

        response = client.get(f"/analysis/{vcf_id}/high-risk-variants")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["variant_id"] == "rs1"
    assert data[0]["gene"] == "BRCA1"
    assert data[0]["clinical_significance"] == "Pathogenic"

    assert data[1]["variant_id"] == "rs2"
    assert data[1]["gene"] == "TP53"
    assert data[1]["clinical_significance"] == "Likely_pathogenic"


def test_high_risk_variants_custom_thresholds():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs1\tA\tG\t150\tPASS\tAF=0.20
1\t200\trs2\tC\tT\t250\tPASS\tAF=0.40
"""

    annotation_content = """#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele
1\tsingle nucleotide variant\tVariant 1\t100\tBRCA1\tPathogenic\trs1\t1\t100\t100\tA\tG
2\tsingle nucleotide variant\tVariant 2\t200\tTP53\tLikely_pathogenic\trs2\t1\t200\t200\tC\tT
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "High Risk Threshold Project",
                "description": "Test custom thresholds",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "thresholds.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )
        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "thresholds.tsv",
                    annotation_content,
                    "text/plain",
                )
            },
        )
        assert annotation_response.status_code == 201

        annotate_response = client.post(f"/analysis/{vcf_id}/annotate")
        assert annotate_response.status_code == 200

        response = client.get(
            f"/analysis/{vcf_id}/high-risk-variants",
            params={
                "min_qual": 200,
                "min_af": 0.3,
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["variant_id"] == "rs2"
    assert data[0]["gene"] == "TP53"


def test_high_risk_variants_vcf_not_found():
    with TestClient(app) as client:
        response = client.get("/analysis/999999/high-risk-variants")

    assert response.status_code == 404
    assert response.json()["detail"] == "VCF file not found."
