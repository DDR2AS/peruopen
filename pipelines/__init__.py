"""La cocina de peruopen: extrae, limpia, valida y publica los datos.

Solo corre en CI o en local con `pip install -e ".[pipeline]"`. La librería
pública (`src/peruopen/`) nunca importa nada de aquí.

    python -m pipelines build                         # extrae + valida + Parquet
    python -m pipelines publish --target local --dir data/vitrina
    python -m pipelines publish --target r2           # usa las variables R2_*
"""
