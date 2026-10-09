# Shim: keithley2000/2182/6221 drivers expect ``from .buffer import KeithleyBuffer``.
# Re-export pymeasure's implementation so no local copy is needed.
from pymeasure.instruments.keithley.buffer import KeithleyBuffer  # noqa: F401
