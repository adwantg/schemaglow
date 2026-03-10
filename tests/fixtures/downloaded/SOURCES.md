# Downloaded Sample Sources

These files are committed so local testing does not depend on live network access.

## Files

- `seattle-weather.csv`  
  Source: <https://raw.githubusercontent.com/vega/vega-datasets/main/data/seattle-weather.csv>
- `miserables.json`  
  Source: <https://raw.githubusercontent.com/vega/vega-datasets/main/data/miserables.json>
- `example.jsonl`  
  Source: <https://gist.githubusercontent.com/rfmcnally/0a5a16e09374da7dd478ffbe6ba52503/raw/ndjson-sample.json>
- `alltypes_plain.parquet`  
  Source: <https://raw.githubusercontent.com/apache/parquet-testing/master/data/alltypes_plain.parquet>
- `petstore.yaml`  
  Source: <https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml>
- `user.avsc`  
  Source: <https://gist.githubusercontent.com/r39132/f94484efa68a8ca4d2d23a4260436c7a/raw/user.avsc>
- `addressbook.proto`  
  Source: <https://raw.githubusercontent.com/protocolbuffers/protobuf/main/examples/addressbook.proto>

## Derived Fixtures

The files under `tests/fixtures/manual/` are small baseline/candidate variants derived from these
downloaded sources. They are the fixtures used by the committed roadmap smoke tests and by
`TESTING.md`.
