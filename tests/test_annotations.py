from fastapi.testclient import TestClient

from app.main import app


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
