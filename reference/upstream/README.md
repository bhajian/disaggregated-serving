# Vendored upstream schemas

[Home](../../README.md) › [Reference](../README.md) › Upstream

Schemas extracted from pinned upstream releases for offline validation by
[tools/validate.py](../../tools/validate.py). See
[upstream-verification.md](../upstream-verification.md) for what was checked.

- [dynamo-v1.4.0/](dynamo-v1.4.0/): served `openAPIV3Schema` of the DynamoGraphDeployment
  (v1beta1, v1alpha1) and DynamoGraphDeploymentRequest (v1beta1) CRDs. Regenerate with
  `python tools/vendor_crds.py <dynamo-v1.4.0 checkout>`; `index.json` records each
  source file's SHA256.
