---
name: New file
about: Propose a new model input to add to the datapackage.
title: ''
labels: ''
assignees: ''
---

## Overview

- What file should we add?
- Where should the data in this file come from? If different columns should come from different sources, which source(s) should be used for each column?
- What connections does this file have to other parts of the datapackage? e.g., foreign key constraints ("Every $column value in this file must be listed in $other_table" "$column must contain every value listed in $other_table\[$other_column]") or input pipeline constraints ("When constructing $other_table, only include EIA records listed in $this_table[$column\]")
- By default we will check column name, type, order, any constraints listed in the field spec below, and any connections listed above. If a modeler wishes to provide their own copy of this file, what additional data validation checks must it pass?

## Datapackage spec

Fill in every $VARIABLE below, removing any optional lines that aren't needed.

```json
{
    "name": "$NAME",
    "type": "table",
    "path": "out/$CATEGORY/$NAME.csv",
    "scheme": "file",
    "format": "csv",
    "mediatype": "text/csv",
    "encoding": "utf-8",
    "description": "$DESCRIPTION.",
    "schema": {
        "fields": [
            { # replicate for each column in the file
                "name": "$COLUMN",
                "type": "$COLUMN_TYPE",
                "unit": "$COLUMN_UNIT", # optional
                "constraints": { # optional
                  "$CONSTRAINT_TYPE": $CONSTRAINT_VALUE # optional
                }, # optional
                "description": "$COLUMN_DESCRIPTION" # optional
            }
        ]
    }
}
```
