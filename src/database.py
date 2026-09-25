"""database.py

Conexão com PostgreSQL com suporte a psycopg v3/v2 e auto-resolução de host e
porta.
"""

from datetime import datetime, timedelta
import logging
import os
from typing import Optional

try:
  import psycopg
except ImportError:
  try:
    import psycopg2 as psycopg
  except ImportError:
    psycopg = None

logger = logging.getLogger(__name__)


class Database:

  def __init__(self, config: dict):
    if psycopg is None:
      raise ImportError(
          'Nenhum driver PostgreSQL encontrado. Instale com: pip install'
          ' "psycopg[binary]"'
      )

    self.dias = config.get('banco_dados', {}).get('dias_para_reenviar', 7)
    self.host = os.getenv('DB_HOST', 'localhost')
    self.port = int(os.getenv('DB_PORT', '5433'))
    self.user = os.getenv('DB_USER', 'postgres')
    self.password = os.getenv('DB_PASSWORD', 'postgres')
    self.dbname = os.getenv('DB_NAME', 'robo_afiliados')

    self._criar_tabelas()

  def _conectar(self):
    """Tenta conectar ao PostgreSQL testando os hosts e portas disponíveis."""
    tentativas = [
        (self.host, self.port),
        ('localhost', 5433),
        ('127.0.0.1', 5433),
        ('postgres', 5432),
        ('postgres_afiliados', 5432),
        ('localhost', 5432),
    ]

    # Remove duplicados mantendo a ordem
    combinacoes = []
    for h, p in tentativas:
      if (h, p) not in combinacoes:
        combinacoes.append((h, p))

    ultimo_erro = None
    for h, p in combinacoes:
      try:
        conn = psycopg.connect(
            host=h,
            port=p,
            user=self.user,
            password=self.password,
            dbname=self.dbname,
            connect_timeout=3,
        )
        logger.info(f"PostgreSQL conectado com sucesso em '{h}:{p}'")
        return conn
      except Exception as e:
        ultimo_erro = e
        continue

    logger.critical(
        f'Falha ao conectar ao PostgreSQL. Tentativas esgotadas: {combinacoes}'
    )
    raise ultimo_erro

  def _criar_tabelas(self):
    with self._conectar() as conn:
      with conn.cursor() as cur:
        cur.execute("""
                    CREATE TABLE IF NOT EXISTS enviados (
                        id          SERIAL PRIMARY KEY,
                        produto_id  VARCHAR(100) NOT NULL,
                        nicho_id    VARCHAR(100),
                        grupo_id    VARCHAR(150) NOT NULL,
                        plataforma  VARCHAR(50) NOT NULL,
                        enviado_em  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_produto_grupo_plataforma
                    ON enviados (produto_id, grupo_id, plataforma);
                """)
      conn.commit()

  def ja_enviado(
      self, produto_id: str, grupo_id: str, plataforma: str
  ) -> bool:
    limite = datetime.now() - timedelta(days=self.dias)
    query = """
            SELECT 1 FROM enviados
            WHERE produto_id = %s AND grupo_id = %s AND plataforma = %s
            AND enviado_em > %s
            LIMIT 1;
        """
    try:
      with self._conectar() as conn:
        with conn.cursor() as cur:
          cur.execute(query, (produto_id, grupo_id, plataforma, limite))
          return cur.fetchone() is not None
    except Exception as e:
      logger.error(f'Erro ao consultar duplicidade: {e}')
      return False

  def registrar(
      self,
      produto_id: str,
      grupo_id: str,
      plataforma: str,
      nicho_id: Optional[str] = None,
  ):
    query = """
            INSERT INTO enviados (produto_id, grupo_id, plataforma, nicho_id, enviado_em)
            VALUES (%s, %s, %s, %s, %s);
        """
    try:
      with self._conectar() as conn:
        with conn.cursor() as cur:
          cur.execute(
              query,
              (
                  produto_id,
                  grupo_id,
                  plataforma,
                  nicho_id,
                  datetime.now(),
              ),
          )
        conn.commit()
    except Exception as e:
      logger.error(f'Erro ao registrar envio: {e}')

  def estatisticas(self) -> dict:
    limite = datetime.now() - timedelta(days=7)
    try:
      with self._conectar() as conn:
        with conn.cursor() as cur:
          cur.execute(
              'SELECT COUNT(*) FROM enviados WHERE enviado_em > %s;',
              (limite,),
          )
          total = cur.fetchone()[0]
          cur.execute(
              """
                        SELECT plataforma, COUNT(*) FROM enviados
                        WHERE enviado_em > %s GROUP BY plataforma;
                    """,
              (limite,),
          )
          por_plat = cur.fetchall()
      return {'total_7d': total, 'por_plataforma': dict(por_plat)}
    except Exception as e:
      return {'total_7d': 0, 'por_plataforma': {}}