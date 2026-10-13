"""Tests never touch the network: the Reloj data comes from the vendored snapshot."""
import os

os.environ["EQUITYVAL_OFFLINE"] = "1"
