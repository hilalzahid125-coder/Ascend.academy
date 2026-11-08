"""PostgreSQL adapter for the app's existing parameterized SQL.

The SQLite app uses ? placeholders and double-quoted string literals. This
adapter converts those SQL tokens for PostgreSQL without interpolating values.
"""
import re
import os
import psycopg
from psycopg.rows import dict_row


def _postgres_sql(sql, has_parameters):
    out = []
    i = 0
    while i < len(sql):
        char = sql[i]
        if char in ("'", '"'):
            quote = char
            end = i + 1
            chars = []
            while end < len(sql):
                if sql[end] == quote:
                    if end + 1 < len(sql) and sql[end + 1] == quote:
                        chars.append(quote)
                        end += 2
                        continue
                    break
                chars.append(sql[end]); end += 1
            if end >= len(sql):
                raise ValueError('Unterminated SQL string')
            value = ''.join(chars).replace("'", "''")
            if has_parameters:
                value = value.replace('%', '%%')
            out.append("'" + value + "'")
            i = end + 1
        elif char == '?':
            out.append('%s'); i += 1
        elif char == '%' and has_parameters:
            out.append('%%'); i += 1
        else:
            out.append(char); i += 1
    result = ''.join(out)
    if re.match(r'^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+', result, re.I):
        result = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', result, count=1, flags=re.I)
        result = result.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    return result


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            # All workflows that require SQLite's writer lock share this lock.
            return self.connection.execute('SELECT pg_advisory_xact_lock(638418624)')
        query = _postgres_sql(sql, bool(params))
        return self.connection.execute(query, params or None)


def open_postgres(url):
    options = {'sslmode': 'require'} if os.getenv('VERCEL') == '1' else {}
    conn = psycopg.connect(url, row_factory=dict_row, prepare_threshold=None, **options)
    conn.execute('SET search_path TO ascend, pg_catalog')
    return conn
