# fenix-retrieval
Gets per-commit performance tests.

### Set up
Create and active a virtualenv:
```sh
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:
```sh
pip install -r csv_gen_reqs.txt
```

### Running
Suggested usage:
```sh
python3 generate_applink_data.py -r FENIX_REPO -c CACHE
```

See `--help` for current default configuration.

Commonly changed arguments include:
- --device
- --test-name
