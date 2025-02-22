# Transfer Logbook Services PRD

## Overview

This document defines the migration of our legacy logbook services into the new asynchronous FastAPI-based architecture under the **services/logbook** directory. The updated system will support two distinct methods for data ingestion:

- **Mountain Project (MTN):** The service calls an API endpoint which returns a CSV (sometimes up to 5 seconds later).
- **8a.nu:** The user provides 8a.nu credentials to authenticate; once authenticated, the system scrapes their data from the active session, converts it to CSV via an existing tool, and processes it as with the MTN data.

Once a CSV is obtained (or JSON data transformed to CSV format), the orchestrator will invoke the common processing workflow to generate domain models (i.e., **UserTicks** and **PerformancePyramid**) and delegate saving these models into the database.

## Data Ingestion Strategies

The system implements two distinct ingestion strategies that reflect the differences in access methods and protection mechanisms employed by the data sources.

For **Mountain Project**, an asynchronous HTTP client using **httpx** is used. This client makes direct REST API calls to fetch CSV data. Since the Mountain Project endpoint is designed to deliver CSV content quickly and does not provide advanced anti-scraping measures, the httpx-based approach is efficient and straightforward. Data is fetched asynchronously, ensuring that the call does not block other operations in the FastAPI environment.

In contrast, **8a.nu** employs multiple layers of protection and a complex authentication flow with Keycloak. To address these challenges, a headless browser strategy using **Playwright** is adopted. With Playwright, the user is presented with an interactive login page to complete the authentication process. The headless browser preserves all session state (including HttpOnly cookies, local storage tokens, and other authentication details) once the user logs in. After this step, the browser session is used to call the JSON endpoints (for example, for ascent data) directly. This JSON data can then be converted into a CSV or processed directly by our transformation pipeline. By leveraging a browser environment, the system reliably simulates genuine user behavior and circumvents the brittleness associated with manual HTML parsing and token extraction.

## Rationale

Our legacy logbook services were implemented using Flask with synchronous calls to external APIs and file retrieval mechanisms. Transitioning to FastAPI unlocks improved performance and maintainability through asynchronous operations, explicit dependency injection, and structured error handling. With the new design, both CSV sources are unified into a single processing pipeline while accommodating their specific retrieval requirements. Centralizing data transformation logic, separating retrieval from processing, and isolating database operations makes the system scalable and adaptable for future data sources.

## Scope and Objectives

The updated logbook service must:

- Retrieve CSV data asynchronously from Mountain Project by directly calling its API endpoint.
- For 8a.nu, use stored credentials to authenticate and then scrape the user's data; convert the scraped data to CSV format.
- Process the CSV data using common logic found in a **base processor**, and—when necessary—source-specific processors (e.g., **mp_csv_processor.py** for MTN and **8a_csv_processor.py** for 8a.nu).
- Leverage the **climb_classifier** to create the **UserTicks** object and then build the **PerformancePyramid** from the processed data.
- Upload the processed data to persist the **UserTicks** and **PerformancePyramid** using asynchronous database sessions via a dedicated persistence module.
- Integrate comprehensive error handling and structured logging.

## Functional Requirements

All CSV retrieval and transformation functions must be fully asynchronous using Python's `async/await` syntax. The orchestrator is responsible for determining the data source based on input parameters. For Mountain Project, it calls the **mp_csv_client.py** which uses an httpx-based GET to retrieve CSV data. For 8a.nu, after the user completes the interactive authentication flow via Playwright, the orchestrator leverages the scraper in **8a_scraper.py** to directly call the JSON API endpoint and convert it to CSV. This endpoint is similar to:

```
https://www.8a.nu/unificationAPI/ascent/v1/web/users/<user_slug>/ascents?category=sportclimbing&pageIndex=0&pageSize=50&sortField=<sort_metric>&timeFilter=0&gradeFilter=0&typeFilter=&includeProjects=false&searchQuery=&showRepeats=false&showDuplicates=false
```

where multiple requests with different parameters are made to fetch all the data for a user.

The retrieved data (JSON) is transformed to csv and continues to the shared processing layer, ensuring uniform transformation regardless of source.

## Persistence Workflow

After processing, the **UserTicks** and **PerformancePyramid** models are built through the **climb_classifier** and **pyramid_builder** modules, respectively. The orchestrator then uses the persistence module (**database_service.py**) to commit these models asynchronously to the database using a dedicated asynchronous database session. This maintains a clear separation of concerns and aligns with our scalable, high-concurrency design requirements.

## Non-Functional Requirements

The new logbook service layer must:

- Eliminate synchronous blocking calls by offloading intensive operations to background tasks as needed.
- Maintain a clear separation between data retrieval (gateway layer), transformation (processing layer), and persistence (dedicated database service module).
- Adhere to FastAPI best practices by using dependency injection and asynchronous database sessions.
- Include comprehensive logging and error handling at each stage of the data processing pipeline.
- Be scalable to handle high-concurrency loads and adaptable for future logbook sources.

## Architecture and Design Decisions

The service layer is reorganized under **services/logbook** with clear compartmentalization of responsibilities. The data retrieval components are isolated in a **gateways** directory. The **mp_csv_client.py** is used for Mountain Project, using httpx to perform asynchronous GET requests and handle CSV responses. For 8a.nu, , the solution is implemented in **8a_scraper.py**. This Playwright-based gateway manages interactive authentication and session persistence before retrieving data from the protected JSON endpoints.

The transformation layer comprises a **base_csv_processor.py** for shared CSV parsing and dedicated processors (**mp_csv_processor.py** and **8a_csv_processor.py**) to handle any source-specific data adjustments. The orchestrator in **orchestrator.py** selects the appropriate data retrieval pathway based on input parameters. Post-processing, the **climb_classifier** is used to build the **UserTicks** object and the **pyramid_builder** constructs the **PerformancePyramid**.

The persistence layer in **database_service.py** ensures that the domain models are saved asynchronously with robust error handling and rollback logic. Dependency injection provides the asynchronous database sessions, ensuring that the entire pipeline adheres to FastAPI best practices.

## Implementation Plan

**Phase 1: Environment Setup**  
Establish a dedicated branch for the migration. Reorganize the file structure by creating the **services/logbook** directory with separate subdirectories for **gateways** and **processing**, and add a dedicated persistence module. Update project configurations to include asynchronous libraries and dependencies.

**Phase 2: Gateway and Processor Development**

- Implement and test asynchronous gateway components:
  - `mp_csv_client.py` for calling the Mountain Project API.
  - Establish a robust **httpx**-based client for Mountain Project to reliably fetch CSV data.
    - `eight_a_nu_scraper.py` for scraping 8a.nu data post-authentication.
    - Develop a Playwright-based gateway for 8a.nu in **scraper_playwright.py** that handles interactive user authentication, session preservation, and direct API calls to JSON endpoints.
  - Ensure that both ingestion strategies feed a unified processing and persistence pipeline with rigorous logging and error handling.
- Develop a common processor in `base_csv_processor.py` for CSV parsing and transformation.
- Build source-specific logic in `mp_csv_processor.py` and `a8_csv_processor.py` as needed.

**Phase 3: Orchestration, Persistence, and Integration**

- Refactor legacy orchestration logic from `data_processor.py` into a new `orchestrator.py`.
- Integrate asynchronous dependency injection to provide database sessions.
- Ensure that the orchestrator calls the correct gateway based on the source, processes the CSV with the appropriate processor, and leverages **climb_classifier** to generate **UserTicks**.
- Build the **PerformancePyramid** from the processed data.
- Invoke the persistence function from **database_service.py** to commit both the **UserTicks** and **PerformancePyramid** models asynchronously.

**Phase 4: Testing, Documentation, and Deployment**

- Develop asynchronous unit and integration tests for each component.
- Update documentation and migration guides.
- Deploy the new logbook service in phased stages with performance benchmarks and a robust rollback plan.

## Acceptance Criteria and Rollback Plan

The migration is deemed successful when:

- CSV data is fetched asynchronously from both Mountain Project and 8a.nu.
- The orchestrator correctly invokes the base and source-specific processors.
- **UserTicks** and **PerformancePyramid** models are successfully built and saved using asynchronous operations.
- The persistence workflow reliably uses a centralized database service approach without direct DB operations inside individual service modules.
- The system meets performance benchmarks (e.g., handling multi-second delays in API responses, high concurrency) and logs detailed execution and error data.
- A rollback plan is in place, preserving a branch with legacy implementations in case issues arise.

## Risk Management

Potential risks include changes to the 8a.nu authentication flow, token obsolescence, or intermittent scraping blocks. Mitigation strategies involve employing Playwright for a more resilient simulation of user interactions and thorough logging of session and network metrics. In the case of Mountain Project, the simpler API call mitigates most unexpected changes, but systematic monitoring is necessary to capture any deviations. A rollback plan includes preserving legacy implementations and incremental deployment strategies to minimize production impact.

---

_Sources and further reading:_

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Playwright for Python](https://playwright.dev/python/)
- [httpx Documentation](https://www.python-httpx.org/)
- [Advanced Async Patterns in Python](https://realpython.com/async-io-python/)
- [Flask to FastAPI Migration Guidelines](https://testdriven.io/blog/moving-from-flask-to-fastapi/)
- [Async Database Sessions PRD](../docs/async_database_sessions.md)
- [Update Service Layer PRD](../docs/update_service_layer.md)
- [Migration Overview](../docs/migration_overview.md)

## New FastAPIFile Tree

```
../app_fastapi
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── auth.py
│       │   ├── chat.py
│       │   ├── data.py
│       │   ├── payment.py
│       │   ├── user.py
│       │   ├── view_routes.py
│       │   └── visualization.py
│       └── router.py
├── assets/
│   └── css/
│       └── tailwind.css
├── core/
│   ├── auth.py
│   ├── config.py
│   ├── error_handlers.py
│   ├── exceptions.py
│   └── logging.py
├── db/
│   ├── base.py
│   ├── base_class.py
│   └── session.py
├── main.py
├── models/
│   ├── chat.py
│   ├── climbing.py
│   └── user.py
├── schemas/
│   ├── auth.py
│   ├── chat.py
│   ├── data.py
│   ├── payment.py
│   ├── user.py
│   └── visualization.py
├── services/
│   ├── dashboard_analytics.py
│   ├── grade_service.py
│   └── logbook/
│       ├── climb_classifier.py
│       ├── database_service.py
│       ├── gateways/
│       │   ├── 8a_scraper.py
│       │   └── mp_csv_client.py
│       ├── orchestrator.py
│       ├── processing/
│       │   ├── 8a_csv_processor.py
│       │   ├── base_csv_processor.py
│       │   └── mp_csv_processor.py
│       └── pyramid_builder.py
├── static/
│   ├── css/
│   │   └── tailwind.css
│   ├── images/
│   └── js/
├── templates/
│   └── base.html
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_data.py
    ├── test_payment.py
    └── test_visualization.py
```
