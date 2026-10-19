from importlib.resources import files
import psycopg
from .config import settings


def main():
    config = settings()
    sql = files('knowledge').joinpath('migrations/001_initial.sql').read_text()
    with psycopg.connect(config.database_url) as db:
        db.execute(sql.replace('__DIMENSIONS__', str(config.embedding_dimensions)))
        actual = db.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute WHERE attrelid='chunks'::regclass AND attname='embedding'").fetchone()[0]
        if actual != f'vector({config.embedding_dimensions})':
            raise ValueError('Embedding dimension migration required; existing schema was preserved')


if __name__ == '__main__':
    main()
