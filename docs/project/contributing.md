# Contributing

Install Python 3.12 and Rust stable, then run the local checks:

```sh
python -m pip install -e .
./scripts/check.sh
```

For documentation work:

```sh
python -m pip install -r docs/requirements.txt
./scripts/docs-check.sh
zensical serve
```

Keep Python as the application language and Rust as the native lifecycle
layer. Bridge changes need origin checks, allowlisted methods, bounds,
structured errors, and positive and negative tests. Do not add GitHub Actions
or `.github/workflows` files. Read [CONTRIBUTING.md](https://github.com/yuzaiakira/kourosh.py/blob/work/CONTRIBUTING.md)
for the commit identity and verification rules.
