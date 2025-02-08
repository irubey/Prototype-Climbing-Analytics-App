# ClimberSummary Form Elements

This document details each field in the **ClimberSummary** model and the recommended HTML input type to use in the user interface.

| **ClimberSummary Field**                 | **Recommended HTML Input Element**                                                             |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `highest_sport_grade_tried`              | `<input type="text">`                                                                          |
| `highest_trad_grade_tried`               | `<input type="text">`                                                                          |
| `highest_boulder_grade_tried`            | `<input type="text">`                                                                          |
| `total_climbs`                           | `<input type="number">`                                                                        |
| `favorite_discipline`                    | `<select>` with options: "tr", "boulder", "sport", "trad", "mixed", "winter_ice", "aid"        |
| `years_climbing_outside`                 | `<input type="number" step="1">`                                                               |
| `preferred_crag_last_year`               | `<input type="text">`                                                                          |
| `training_frequency`                     | `<select>` (or `<input type="text">` for freeform entries)                                     |
| `typical_session_length`                 | `<select>` with options: "Less than 1 hour", "1-2 hours", "2-3 hours", "3-4 hours", "4+ hours" |
| `has_hangboard`                          | `<input type="checkbox">`                                                                      |
| `has_home_wall`                          | `<input type="checkbox">`                                                                      |
| `goes_to_gym`                            | `<input type="checkbox">`                                                                      |
| `highest_grade_sport_sent_clean_on_lead` | `<input type="text">`                                                                          |
| `highest_grade_tr_sent_clean`            | `<input type="text">`                                                                          |
| `highest_grade_trad_sent_clean_on_lead`  | `<input type="text">`                                                                          |
| `highest_grade_boulder_sent_clean`       | `<input type="text">`                                                                          |
| `onsight_grade_sport`                    | `<input type="text">`                                                                          |
| `onsight_grade_trad`                     | `<input type="text">`                                                                          |
| `flash_grade_boulder`                    | `<input type="text">`                                                                          |
| `current_injuries`                       | `<textarea>`                                                                                   |
| `injury_history`                         | `<textarea>`                                                                                   |
| `physical_limitations`                   | `<textarea>`                                                                                   |
| `climbing_goals`                         | `<textarea>`                                                                                   |
| `willing_to_train_indoors`               | `<input type="checkbox">`                                                                      |
| `sends_last_30_days`                     | `<input type="number">`                                                                        |
| `current_projects`                       | `<textarea>`                                                                                   |
| `favorite_angle`                         | `<select>` with options: "Slab", "Vertical", "Overhang", "Roof"                                |
| `weakest_angle`                          | `<select>` with options: "Slab", "Vertical", "Overhang", "Roof"                                |
| `strongest_angle`                        | `<select>` with options: "Slab", "Vertical", "Overhang", "Roof"                                |
| `favorite_energy_type`                   | `<select>` with options: "Power", "Power Endurance", "Endurance", "Technique"                  |
| `weakest_energy_type`                    | `<select>` with options: "Power", "Power Endurance", "Endurance", "Technique"                  |
| `strongest_energy_type`                  | `<select>` with options: "Power", "Power Endurance", "Endurance", "Technique"                  |
| `favorite_hold_types`                    | `<select>` with options: "Crimps", "Slopers", "Pockets", "Pinches", "Cracks"                   |
| `weakest_hold_types`                     | `<select>` with options: "Crimps", "Slopers", "Pockets", "Pinches", "Cracks"                   |
| `strongest_hold_types`                   | `<select>` with options: "Crimps", "Slopers", "Pockets", "Pinches", "Cracks"                   |
| `sleep_score`                            | `<select>` with options: "Poor", "Fair", "Good", "Excellent"                                   |
| `nutrition_score`                        | `<select>` with options: "Poor", "Fair", "Good", "Excellent"                                   |
| `additional_notes`                       | `<textarea>`                                                                                   |
