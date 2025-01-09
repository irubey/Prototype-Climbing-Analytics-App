# Pipeline Analysis Results

## Overview

Analysis comparing the old and new climbing data pipeline outputs, focusing on classification changes, data quality improvements, and pattern recognition.

## Key Findings

### 1. Discipline Reclassifications

- **Total Changes**: 59 routes reclassified
- **Sport to TR**: 42 routes
- **Trad to TR**: 17 routes

### 2. Send Status Impact

#### Sport to TR Changes (42 routes)

- All maintained `send_bool: False`
- Lead styles removed when reclassified

#### Trad to TR Changes (17 routes)

- 15 routes maintained `send_bool: False`
- 2 routes changed from `send_bool: True` to `False`
- Lead styles (e.g., "Onsight") removed when reclassified

### 3. Location Patterns

#### Sport to TR Changes

- Primary locations:
  - North Table Mountain/Golden Cliffs
  - Staunton State Park
- Examples:
  - White Walker (5.4)
  - Cool Water Sandwich (5.10c)
  - No Gumbies (5.10d)

#### Trad to TR Changes

- Primary locations:
  - Eldorado Canyon State Park
  - Lookout Mountain Road
- Notable examples:
  - Ruper (5.8+)
  - Rewritten (5.7)

### 4. Route Characteristics

#### Old Data

- **Sport Pyramid Distribution**:
  - Power: 16 routes
  - Power Endurance: 14 routes
  - Endurance: 13 routes
- **Style Distribution**:
  - Vertical: 15 routes
  - Overhang: 15 routes
  - Roof: 7 routes
  - Slab: 6 routes

#### New Data

- Characteristic and style distributions cleared
- Focus on accurate discipline classification

### 5. Length Categories

- Multiple routes properly classified as multipitch
- Length values remain as `nan`
- Indicates improved categorization without specific length data

## Data Quality Improvements

### 1. Classification Accuracy

- More precise discipline categorization
- Removal of inappropriate lead styles for TR ascents
- Conservative send classification

### 2. Data Consistency

- Duplicate entry consolidation
- Proper multipitch flagging
- Standardized discipline classifications

### 3. Notable Route Examples

#### Ruper (5.8+)

- Multiple entries consolidated
- Proper TR classification applied
- Lead style information updated

#### Rewritten (5.7)

- Similar cleanup pattern to Ruper
- Consistent classification approach

## Conclusion

The pipeline changes demonstrate a systematic improvement in data quality, focusing on accurate classification and consistent representation of climbing activities. The changes particularly impact discipline classification and send status determination, with a clear pattern of more conservative and accurate categorization.
