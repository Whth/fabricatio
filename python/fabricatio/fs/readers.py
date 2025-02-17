"""Filesystem readers for Fabricatio."""

from magika import Magika

from fabricatio.config import configs

magika = Magika(model_dir=configs.magika.model_dir)
