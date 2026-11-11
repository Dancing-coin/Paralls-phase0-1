These fixtures were frozen from the Store at commit `4f24dfce` before epoch
format changes. `snapshot-v2.json` is the Store's serialized output for the
existing `_batch()` fixture. `snapshot-v1-derived.json` was derived from that
output by changing the version to 1 and removing the v2 event schema registry;
the old Store accepted it. It is a compatibility sample, not an archived v1
production snapshot. Their file hashes and ledger hashes are fixed in
`test_authority_epoch_snapshot.py`.
