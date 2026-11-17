from app.gameplay.credential_runtime import CredentialPresentationValidator
from g3_credential_fixture import command, setup_reference


def test_presentation_accepts_pack_declared_v2_kind():
    store, registry, chain = setup_reference()
    chain._owner.activate_v2_authority()
    args = command("issue_credential") | {"credential_kind": "permit"}
    assert chain.execute("issue_credential", **args).committed
    params = chain.pack.registry.models["credential_command@1"].params
    validator = CredentialPresentationValidator(store=store, inventory_registry=registry,
        credential_kinds=params["credential_kinds"], proves=params["proves"])
    assert validator.verify_right_holder_presentation(
        credential_id=args["credential_id"], presenter_ref=args["credential_holder_ref"]
    ).authorized
