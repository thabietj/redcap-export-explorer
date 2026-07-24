# REDCap Export Explorer

A privacy-preserving, local tool for inspecting, linking, selecting, validating, and exporting multiple REDCap datasets.

> All processing occurs locally. No data are transmitted externally.

## Install and run

Python 3.9+ is required. In this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
streamlit run app.py
```

The first installation needs access to a Python package source. Once installed, the application works offline. It makes no runtime network requests.

## Try the fictional data

Open the local address shown by Streamlit. Upload the five data CSVs from `synthetic_data/`; optionally upload `redcap_data_dictionary.csv` in the separate metadata box. Move through the eight sidebar steps. Try linking diagnoses and medications on `record_id` to see the intentional many-to-many warning. All names, addresses, codes, and observations are fictional.

## Tests

```bash
pytest -q
```

The suite covers imports and encoding, inference, name cleaning and collisions, shared variables, identifier scores, composite keys/cardinality, unsafe joins, checkbox/date/missing handling, Stata and Excel export, project round-trips, schema differences, and a source-level no-network guard.

See [the architecture](docs/ARCHITECTURE.md) for design and phase boundaries.

## Phase 2 features

Saved JSON projects capture source hashes, schemas, selections, linkage keys, structure overrides, checkbox modes and REDCap metadata. Reloading a project compares the current exports with the saved schemas and blocks export when required variables have disappeared. REDCap labels and coded choices are used for inspection, validation, and Stata value labels. Checkbox groups can remain as binary indicators or become combined code strings, combined label strings, or long-format tables.

## Phase 3 and desktop build

The preparation recipe supports renaming, trimming, case normalization, strict type conversion, date parts, binary indicators, row totals, duplicate removal, age derivation, aggregation, and long/wide reshaping in the engine. The interface offers the most common actions with previews and saves them in the project. Flat exports use confirmed relationships and still require explicit consent for a many-to-many join.

Installer build scripts are provided for macOS and Windows. PyInstaller must run on the target operating system; Windows executables cannot be compiled on macOS. The macOS script produces a `.pkg` installer.

```bash
python -m pip install -e '.[desktop]'
sh packaging/build_macos.sh
```

The resulting bundle is placed in `dist/`. See [packaging instructions](packaging/README.md) for the Windows Inno Setup build and signing notes. The packaged application binds only to `127.0.0.1`, disables usage telemetry, and includes all processing dependencies. Build tools are not needed on the researcher's computer.
