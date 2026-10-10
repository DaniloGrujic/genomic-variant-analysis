import gzip

from fastapi.testclient import TestClient

from app.main import app


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


def test_upload_vcf_stores_quality():
    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
1\t12345\trs123\tA\tG\t150.5\tPASS\tAF=0.25
"""

    with TestClient(app) as client:
        project_response = client.post(
            "/projects/",
            json={
                "name": "Quality Test Project",
                "description": "Test VCF quality parsing",
            },
        )

        assert project_response.status_code == 201

        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "quality_test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201

        vcf_id = upload_response.json()["id"]

        response = client.get(
            f"/projects/{project_id}/vcf/{vcf_id}",
        )

    assert response.status_code == 200

    data = response.json()

    assert data["variants"][0]["quality"] == 150.5
