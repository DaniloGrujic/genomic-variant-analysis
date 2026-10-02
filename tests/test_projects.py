import gzip

from fastapi.testclient import TestClient

from app.main import app


def test_create_project():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "Test Project",
                "description": "Test description",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "Test description"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_project_with_too_long_name():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "A" * 256,
                "description": "Test description",
            },
        )

    assert response.status_code == 422


def test_create_project_with_empty_name():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "",
                "description": "Test description",
            },
        )

    assert response.status_code == 422


def test_create_project_without_description():
    with TestClient(app) as client:
        response = client.post(
            "/projects/",
            json={
                "name": "Project Without Description",
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Project Without Description"
    assert data["description"] is None


def test_get_projects():
    with TestClient(app) as client:
        create_response = client.post(
            "/projects/",
            json={
                "name": "Test Project",
                "description": "Test description",
            },
        )

        assert create_response.status_code == 201

        response = client.get("/projects/")

    assert response.status_code == 200
    data = response.json()
    assert any(project["name"] == "Test Project" for project in data)


def test_delete_project():
    with TestClient(app) as client:
        create_response = client.post(
            "/projects/",
            json={
                "name": "Project to Delete",
                "description": "Test description",
            },
        )

        assert create_response.status_code == 201

        project_id = create_response.json()["id"]

        delete_response = client.delete(f"/projects/{project_id}/")

    assert delete_response.status_code == 204


def test_upload_vcf():
    vcf_content = """##fileformat=VCFv4.2
##INFO=<ID=AF,Number=A,Type=Float,Description="Allele Frequency">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t.\tPASS\tAF=0.25
2\t200\t.\tC\tT\t.\tPASS\tAF=0.75
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "VCF Test Project",
                "description": "Project for VCF upload test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == project_id
    assert data["filename"] == "test.vcf"
    assert data["file_size"] == len(vcf_content.encode("utf-8"))
    assert data["variant_count"] == 2
    assert "id" in data
    assert "created_at" in data


def test_upload_invalid_vcf_extension():
    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Invalid VCF Test",
                "description": "Project for invalid VCF upload test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.txt",
                    "not a VCF file",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == ("Only .vcf and .vcf.gz files are allowed.")


def test_get_vcf_files():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t.\tPASS\tAF=0.25
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "VCF List Test",
                "description": "Project for VCF list test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201

        response = client.get(f"/projects/{project_id}/vcf/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["project_id"] == project_id
    assert data[0]["filename"] == "test.vcf"
    assert data[0]["variant_count"] == 1


def test_get_vcf_file():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t.\tPASS\tAF=0.25
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Single VCF Test",
                "description": "Project for single VCF test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201

        vcf_id = upload_response.json()["id"]

        response = client.get(f"/projects/{project_id}/vcf/{vcf_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == vcf_id
    assert data["project_id"] == project_id
    assert data["filename"] == "test.vcf"
    assert data["variant_count"] == 1

    assert len(data["variants"]) == 1

    variant = data["variants"][0]

    assert variant["chromosome"] == "1"
    assert variant["position"] == 100
    assert variant["variant_id"] == "rs123"
    assert variant["reference"] == "A"
    assert variant["alternate"] == "G"
    assert variant["allele_frequency"] == 0.25


def test_get_vcf_file_not_found():
    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Missing VCF Test",
                "description": "Project for missing VCF test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        response = client.get(f"/projects/{project_id}/vcf/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "VCF file not found"


def test_delete_vcf_file():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t.\tPASS\tAF=0.25
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Delete VCF Test",
                "description": "Project for VCF deletion test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "delete_test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201

        vcf_id = upload_response.json()["id"]

        delete_response = client.delete(f"/projects/{project_id}/vcf/{vcf_id}")

        assert delete_response.status_code == 204

        get_response = client.get(f"/projects/{project_id}/vcf/{vcf_id}")

    assert get_response.status_code == 404


def test_upload_annotation():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tNM_001385641.1(TP53):c.743G>A\t"
        "7157\tTP53\tPathogenic\trs28934578\t2\t121746135\t121746135\tC\tT\n"
    )

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Annotation Upload Test",
                "description": "Project for annotation upload test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "clinvar.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == project_id
    assert data["filename"] == "clinvar.tsv"
    assert data["entry_count"] == 1


def test_upload_invalid_annotation_extension():
    annotation_content = """#CHROM\tPOS\tREF\tALT\tGENE\tCLNSIG\tCLNREVSTAT\tCLNDN\tCLNVC\tMC\tORIGIN\tAF
1\t100\tA\tG\tGENE1\tPathogenic\treviewed_by_expert_panel\tDisease1\tSNV\tSO:0001583\t1\t0.25
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Invalid Annotation Test",
                "description": "Project for invalid annotation test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "annotations.csv",
                    annotation_content,
                    "text/csv",
                )
            },
        )

    assert upload_response.status_code == 400
    assert upload_response.json()["detail"] == (
        "Only .txt or .tsv annotation files are allowed."
    )


def test_upload_invalid_annotation_columns():
    annotation_content = """#CHROM\tPOS\tREF\tALT\tGENE\tCLNSIG\tCLNREVSTAT\tCLNDN\tCLNVC\tMC\tORIGIN
1\t100\tA\tG\tGENE1\tPathogenic\treviewed_by_expert_panel\tDisease1\tSNV\tSO:0001583\t1
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Invalid Annotation Columns Test",
                "description": "Project for invalid annotation columns test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "invalid_columns.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )

    assert upload_response.status_code == 400
    assert upload_response.json()["detail"] == (
        "Invalid annotation file: Invalid 12-column ClinVar header."
    )


def test_get_annotation_files():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tNM_001385641.1(TP53):c.743G>A\t"
        "7157\tTP53\tPathogenic\trs28934578\t2\t121746135\t121746135\tC\tT\n"
    )

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Get Annotation Test",
                "description": "Project for getting annotations",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "annotations.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )

        assert upload_response.status_code == 201

        response = client.get(f"/projects/{project_id}/annotation/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["project_id"] == project_id
    assert data[0]["filename"] == "annotations.tsv"
    assert data[0]["entry_count"] == 1


def test_delete_annotation_file():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tNM_001385641.1(TP53):c.743G>A\t"
        "7157\tTP53\tPathogenic\trs28934578\t2\t121746135\t121746135\tC\tT\n"
    )

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Delete Annotation Test",
                "description": "Project for annotation deletion test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "delete_annotation.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )

        assert upload_response.status_code == 201

        annotation_id = upload_response.json()["id"]

        delete_response = client.delete(
            f"/projects/{project_id}/annotation/{annotation_id}"
        )

        assert delete_response.status_code == 204

        get_response = client.get(f"/projects/{project_id}/annotation/")

    assert get_response.status_code == 200
    assert get_response.json() == []


def test_delete_annotation_file_not_found():
    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Delete Missing Annotation Test",
                "description": "Project for missing annotation test",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        delete_response = client.delete(f"/projects/{project_id}/annotation/999999")

    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Annotation file not found"


def test_annotation_counts_only_valid_entries():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        # Valid
        "1\tsingle nucleotide variant\tVariant1\t7157\tTP53\tPathogenic\t"
        "rs1\t2\t100\t100\tA\tG\n"
        # Invalid Start
        "2\tsingle nucleotide variant\tVariant2\t1956\tEGFR\tBenign\t"
        "rs2\t22\tinvalid\t200\tC\tT\n"
        # Invalid VariantID
        "invalid\tsingle nucleotide variant\tVariant3\t672\tBRCA1\t"
        "Likely_pathogenic\trs3\t17\t300\t300\tG\tA\n"
        # Valid chromosome with chr prefix
        "4\tsingle nucleotide variant\tVariant4\t675\tBRCA2\tPathogenic\t"
        "rs4\tchr13\t400\t400\tT\tC\n"
    )

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Annotation Entry Count Test",
                "description": "Project for annotation entry validation",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "clinvar.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["entry_count"] == 2


def test_upload_gzipped_vcf():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t100\trs123\tA\tG\t.\tPASS\tAF=0.25
"""

    compressed_content = gzip.compress(vcf_content.encode("utf-8"))

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Gzipped VCF Test",
                "description": "Project for gzipped VCF upload",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.vcf.gz",
                    compressed_content,
                    "application/gzip",
                )
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["filename"] == "test.vcf.gz"
    assert data["variant_count"] == 1


def test_upload_malformed_vcf():
    vcf_content = """This is not a valid VCF file.
It has a .vcf extension but no VCF header.
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Malformed VCF Test",
                "description": "Project for malformed VCF upload",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "invalid.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

    assert response.status_code == 400
    assert "Invalid VCF file" in response.json()["detail"]


def test_upload_txt_annotation_file():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tNM_001385641.1(TP53):c.743G>A\t"
        "7157\tTP53\tPathogenic\trs28934578\t2\t121746135\t121746135\tC\tT\n"
    )

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "TXT Annotation Test",
                "description": "Project for TXT annotation upload",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "test_variant_summary.txt",
                    annotation_content,
                    "text/plain",
                )
            },
        )

    assert response.status_code == 201

    data = response.json()
    assert data["filename"] == "test_variant_summary.txt"
    assert data["entry_count"] == 1
