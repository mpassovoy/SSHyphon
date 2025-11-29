# Test Coverage Report

This report captures backend coverage from `python -m coverage run -m pytest backend/tests` and frontend coverage from `npm test -- --run --coverage --coverage.reporter=lcov --coverage.reporter=text-summary`.

## Backend (pytest + coverage)
- **Overall coverage:** 51%
- **Total statements:** 1,396
- **Total missed:** 683

## File breakdown
| File | Coverage |
| --- | --- |
| backend/app/activity_log.py | 56% |
| backend/app/auto_sync.py | 26% |
| backend/app/config_store.py | 37% |
| backend/app/jellyfin_service.py | 18% |
| backend/app/main.py | 90% |
| backend/app/models.py | 97% |
| backend/app/sync_service.py | 16% |
| backend/app/versioning.py | 58% |
| backend/tests/conftest.py | 83% |
| backend/tests/test_main.py | 100% |
| backend/tests/test_versioning.py | 100% |

## Frontend (Vitest + V8)
- **Statements:** 48.29% (636/1317)
- **Branches:** 78.04% (128/164)
- **Functions:** 45.28% (24/53)
- **Lines:** 48.29% (636/1317)
