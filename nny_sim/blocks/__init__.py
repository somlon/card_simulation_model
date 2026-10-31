"""블록 체계 — 조립식 카드 효과 (설계 · 진행 규칙: blocks/README.md)"""
from blocks import dsl, lib, build   # noqa: F401
from blocks.build import attach, TemplateMismatch   # noqa: F401


def load_tables():
    """테마별 조립표(blocks/t_*.py)를 모두 불러 dsl.TABLE에 등록한다"""
    import importlib, pkgutil, os
    here = os.path.dirname(__file__)
    for m in sorted(pkgutil.iter_modules([here]), key=lambda m: m.name):
        if m.name.startswith('t_'): importlib.import_module(f'blocks.{m.name}')


load_tables()
