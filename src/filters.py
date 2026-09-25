"""
filters.py
Aplica filtros de nicho, preço, avaliação mínima, palavras-chave e frete.
Suporta herança de filtros gerais com sobrescrita por nicho específico.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FiltroNicho:
    def __init__(self, config: dict):
        self.config = config
        self.filtros_gerais = config.get("filtros_gerais", {})

    def mesclar_filtros(self, nicho_config: Optional[dict]) -> dict:
        """Mescla os filtros gerais com filtros específicos do nicho."""
        filtros = dict(self.filtros_gerais)
        if nicho_config and "filtros" in nicho_config:
            filtros.update(nicho_config["filtros"])
        return filtros

    def filtrar(self, produtos: list[dict], nicho_config: Optional[dict] = None) -> list[dict]:
        """Filtra e ordena os melhores produtos para envio."""
        filtros = self.mesclar_filtros(nicho_config)

        preco_min         = filtros.get("preco_minimo", 0)
        preco_max         = filtros.get("preco_maximo", 999999)
        avaliacao_min     = filtros.get("avaliacao_minima", 0.0)
        min_avaliacoes    = filtros.get("minimo_avaliacoes", 0)
        desconto_min      = filtros.get("desconto_minimo", 0)
        frete_gratis      = filtros.get("frete_gratis", False)
        palavras_ok       = [p.lower() for p in filtros.get("palavras_obrigatorias", [])]
        palavras_block    = [p.lower() for p in filtros.get("palavras_bloqueadas", [])]
        limite            = filtros.get("limite_produtos_por_nicho", 3)

        aprovados = []
        for p in produtos:
            motivo = self._reprovar(
                p, preco_min, preco_max, avaliacao_min,
                min_avaliacoes, desconto_min, frete_gratis,
                palavras_ok, palavras_block
            )
            if motivo:
                logger.debug(f"Reprovado [{p.get('id')}] {p.get('nome')[:35]}... -> {motivo}")
            else:
                aprovados.append(p)

        # Ordena prioritariamente por maior desconto percentual
        aprovados.sort(key=lambda x: (x.get("desconto", 0), x.get("avaliacao", 0)), reverse=True)
        resultado = aprovados[:limite]

        nicho_nome = nicho_config.get("nome", "Geral") if nicho_config else "Geral"
        logger.info(f"[{nicho_nome}] {len(resultado)} produtos aprovados de {len(produtos)} analisados")
        return resultado

    def _reprovar(
        self, p: dict, preco_min: float, preco_max: float,
        avaliacao_min: float, min_avaliacoes: int, desconto_min: int,
        frete_gratis: bool, palavras_ok: list[str], palavras_block: list[str]
    ) -> Optional[str]:
        nome = p.get("nome", "").lower()
        preco = p.get("preco", 0)

        # Preço
        if not (preco_min <= preco <= preco_max):
            return f"preço R${preco:.2f} fora do intervalo (R${preco_min} - R${preco_max})"

        # Avaliação (se houver total de avaliações registrado)
        total_avaliacoes = p.get("total_avaliacoes", 0)
        avaliacao = p.get("avaliacao", 0.0)
        if total_avaliacoes > 0 and total_avaliacoes >= min_avaliacoes:
            if avaliacao < avaliacao_min:
                return f"nota {avaliacao} abaixo de {avaliacao_min}"

        # Desconto mínimo
        if p.get("desconto", 0) < desconto_min:
            return f"desconto {p.get('desconto')}% < {desconto_min}%"

        # Frete Grátis
        if frete_gratis and not p.get("frete_gratis"):
            return "não possui frete grátis"

        # Palavras bloqueadas no título
        for palavra in palavras_block:
            if palavra in nome:
                return f"contém termo bloqueado: '{palavra}'"

        # Palavras obrigatórias
        if palavras_ok:
            if not any(palavra in nome for palavra in palavras_ok):
                return "não contém nenhuma das palavras obrigatórias"

        return None
