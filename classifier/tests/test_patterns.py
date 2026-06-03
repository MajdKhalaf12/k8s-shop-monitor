from classifier.patterns import check_sqli, check_xss, check_recon_path


def test_sqli_union():
    assert check_sqli("/api?q=1 UNION SELECT password FROM users")


def test_xss_script():
    assert check_xss("/search?q=<script>alert(1)</script>")


def test_recon_admin():
    assert check_recon_path("/admin/dashboard") == "/admin"
