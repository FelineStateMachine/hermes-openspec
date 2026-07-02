# Board Search and Filter Delta

## ADDED Requirements

### Requirement: Text filter on board
The board SHALL provide a text input that filters cards across all columns by title, name, or token.

#### Scenario: Filter by title
- **GIVEN** the board has changes with known titles
- **WHEN** the user types a title substring into the filter input
- **THEN** only cards whose title contains the substring case-insensitively are shown

#### Scenario: Filter by token
- **GIVEN** the board has changes with tokens
- **WHEN** the user types a token such as `os_a1b2c3` into the filter input
- **THEN** only cards whose token contains the substring are shown

#### Scenario: Empty filter shows all
- **GIVEN** the filter input has text
- **WHEN** the user clears the filter input
- **THEN** all cards in all visible columns are shown

#### Scenario: No matches
- **GIVEN** the filter input has text that matches no cards
- **WHEN** the board renders
- **THEN** a no-matches empty state is shown instead of an empty set of columns

### Requirement: Archived column toggle
The board SHALL provide a toggle to show or hide the archived column while keeping archived cards visible by default.

#### Scenario: Hide archived
- **GIVEN** the board is showing the archived column
- **WHEN** the user disables the archived toggle
- **THEN** the archived column is not rendered

#### Scenario: Show archived by default
- **GIVEN** the board is loaded for the first time
- **WHEN** the archived column visibility is evaluated
- **THEN** the archived column is visible

### Requirement: Hash deep-link bypass
The board filter SHALL NOT prevent hash-deep-linked items from opening.

#### Scenario: Hash token with active filter
- **GIVEN** the filter input has text that would hide a specific card
- **WHEN** a hash token matching that card is present in the URL
- **THEN** the card's detail dialog opens regardless of the filter
