from defeat_watermarker.adapters.c2pa import C2paTrustPolicy


def test_custom_c2pa_root_uses_current_sdk_trust_model() -> None:
    policy = C2paTrustPolicy(
        trust_anchors_pem="-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n",
        verify_cert_anchors=True,
    )

    settings = policy.to_settings()

    assert settings["verify"] == {"remote_manifest_fetch": False}
    assert settings["trust"]["user_anchors"].startswith("-----BEGIN CERTIFICATE-----")
    assert "1.3.6.1.4.1.62558.2.1" in settings["trust"]["trust_config"]
    assert "1.3.6.1.5.5.7.3.36" in settings["trust"]["trust_config"]


def test_custom_trust_config_can_override_default_ekus() -> None:
    policy = C2paTrustPolicy(trust_config="1.2.3.4\n")

    assert policy.to_settings()["trust"]["trust_config"] == "1.2.3.4\n"
