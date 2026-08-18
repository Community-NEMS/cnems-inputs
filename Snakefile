rule supply_curve:
  input:
    "SupplyCurve.csv"
  output:
    "supply_curve.csv"
  script:
    "src/cnems_inputs/stub_supply_curve.py"
