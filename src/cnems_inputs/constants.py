"""Collection of constants and enums for data pipelines."""

import pandas as pd

EIA_NREL_TECH_MAP = [
    {
        "Technology": "Conventional Steam Coal",
        "NREL ATB Category": "Coal_FE",
        "NREL ATB Detailed Category": "Coal-95%-CCS",
    },
    {
        "Technology": "Conventional Steam Coal",
        "NREL ATB Category": "Coal_FE",
        "NREL ATB Detailed Category": "Coal-99%-CCS",
    },
    {
        "Technology": "Conventional Steam Coal",
        "NREL ATB Category": "Coal_FE",
        "NREL ATB Detailed Category": "Coal-new",
    },
    {
        "Technology": "Coal Integrated Gasification Combined Cycle",
        "NREL ATB Category": "Coal_FE",
        "NREL ATB Detailed Category": "Coal-IGCC",
    },
    {
        "Technology": "Coal Integrated Gasification Combined Cycle",
        "NREL ATB Category": "Coal_FE",
        "NREL ATB Detailed Category": "Coal-IGCC-90%-CCS",
    },
    {
        "Technology": "Petroleum Liquids",
        "NREL ATB Category": pd.NA,
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Natural Gas Steam Turbine",
        "NREL ATB Category": "NaturalGas_FE",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Petroleum Coke",
        "NREL ATB Category": pd.NA,
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "All Other",
        "NREL ATB Category": pd.NA,
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Natural Gas Fired Combustion Turbine",
        "NREL ATB Category": "NaturalGas_FE",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Natural Gas Internal Combustion Engine",
        "NREL ATB Category": "NaturalGas_FE",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Other Natural Gas",
        "NREL ATB Category": "NaturalGas_FE",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Other Gases",
        "NREL ATB Category": "NaturalGas_FE",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Natural Gas Fired Combined Cycle",
        "NREL ATB Category": "NaturalGas_FE",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Hydrogen Generator",
        "NREL ATB Category": pd.NA,
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Nuclear",
        "NREL ATB Category": "Nuclear",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Wood/Wood Waste Biomass",
        "NREL ATB Category": "Biopower",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Other Waste Biomass",
        "NREL ATB Category": "Biopower",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Geothermal",
        "NREL ATB Category": "Geothermal",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Municipal Solid Waste",
        "NREL ATB Category": "Biopower",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Landfill Gas",
        "NREL ATB Category": "Biopower",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Conventional Hydroelectric",
        "NREL ATB Category": "Hydropower",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Hydroelectric Pumped Storage",
        "NREL ATB Category": "Pumped Storage Hydropower",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Batteries",
        "NREL ATB Category": "Commercial Battery Storage",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Batteries",
        "NREL ATB Category": "Residential Battery Storage",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Batteries",
        "NREL ATB Category": "Utility-Scale Battery Storage",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Natural Gas with Compressed Air Storage",
        "NREL ATB Category": "NaturalGas_FE",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Flywheels",
        "NREL ATB Category": pd.NA,
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Offshore Wind Turbine",
        "NREL ATB Category": "OffShoreWind",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Onshore Wind Turbine",
        "NREL ATB Category": "LandBasedWind",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Solar Photovoltaic",
        "NREL ATB Category": "ResPV",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Solar Photovoltaic",
        "NREL ATB Category": "UtilityPV",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Solar Photovoltaic",
        "NREL ATB Category": "CommPV",
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Solar Thermal without Energy Storage",
        "NREL ATB Category": pd.NA,
        "NREL ATB Detailed Category": pd.NA,
    },
    {
        "Technology": "Solar Thermal with Energy Storage",
        "NREL ATB Category": pd.NA,
        "NREL ATB Detailed Category": pd.NA,
    },
]
