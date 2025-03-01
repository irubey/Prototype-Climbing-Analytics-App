# PRD: Modify FastAPI Backend Authentication for NextAuth Compatibility

## Objective

Update the FastAPI backend's `/api/v1/auth/refresh-token` endpoint to accept the refresh token via an `Authorization: Bearer <refresh_token>` header instead of an HttpOnly cookie, enabling seamless integration with NextAuth's JWT-based authentication flow. Maintain existing security features (token rotation, revocation) and ensure backward compatibility for potential cookie-based clients.

## Background

- **Current State:**

  - The backend uses OAuth2 with RS256 JWTs for authentication.
  - `/api/v1/auth/token` issues `access_token` and `refresh_token`, setting the latter as an HttpOnly cookie.
  - `/api/v1/auth/refresh-token` expects `refresh_token` from the cookie, rotates tokens, and sets a new cookie.
  - Tokens are stored in a Token response model (`access_token`, `refresh_token`, `token_type`, `expires_in`).

- **NextAuth Expectation:**

  - Manages tokens in a JWT, expecting to send `refresh_token` in a request (e.g., Authorization header) and receive new tokens in the response body.
  - Does not natively handle HttpOnly cookies for refresh tokens.

- **Problem:**

  - Cookie-based refresh conflicts with NextAuth's token management, requiring a workaround that exposes `refresh_token` client-side and complicates refresh logic.

- **Goal:**
  - Modify the backend to accept `refresh_token` via header, aligning with NextAuth's flow while keeping token rotation and revocation intact.

## Stakeholders

- **Developers:** Backend and frontend teams implementing SendSage.
- **Users:** Climbers using the app, expecting seamless login/refresh.
- **Security Team:** Ensuring token security isn't compromised.

## Requirements

### Endpoint Modification: `/api/v1/auth/refresh-token`

- **Input:**

  - Replace `request.cookies.get("refresh_token")` with `Authorization: Bearer <refresh_token>` header extraction using an updated `get_token_from_header`.
  - Optional: Support both header and cookie inputs, controlled by a `USE_COOKIE_AUTH` setting (default: False).

- **Output:**

  - Return Token model (`access_token`, `refresh_token`, `token_type`, `expires_in`) in the response body.
  - Remove `response.set_cookie` call unless `USE_COOKIE_AUTH` is True.

- **Logic:**

  - Verify the refresh token with `verify_token` (unchanged).
  - Revoke the old refresh token by adding to `RevokedToken`.
  - Generate new `access_token` and `refresh_token` using `create_access_token` and `create_refresh_token`.
  - Preserve single-use token rotation with new `jti` values.

- **Error Handling:**
  - Return 401 if no refresh token is provided or if verification fails.
  - Return 500 for unexpected errors (e.g., database failure).

### Core Auth Updates

- Update `get_token_from_header`:
  - Prioritize Authorization header, fall back to cookie if `USE_COOKIE_AUTH` is True.
  - Example:

```python
async def get_token_from_header(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    if settings.USE_COOKIE_AUTH:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            return refresh_token
    raise HTTPException(status_code=401, detail="Refresh token missing")
```

- Why: Centralizes token extraction, supporting both flows.

## Settings Update

- Add `USE_COOKIE_AUTH: bool` to Settings in `core/config.py`:

```python
USE_COOKIE_AUTH: bool = Field(default=False, description="Use cookie-based refresh token if true, else header")
```

- Why: Allows toggling between header and cookie-based auth for flexibility.

## Schema Adjustments

- **Existing Token:** Already compatible:

```python
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
```

- No Change Needed: NextAuth expects this structure.

- **Database Models**

  - Existing `RevokedToken`: No change needed; used for token rotation.
  - `KeyHistory`: Unchanged; supports RS256 key rotation.

- **Testing Updates**

  - Update `test_auth_endpoints.py`:
    - Add test for header-based refresh.
    - Test fallback cookie behavior if `USE_COOKIE_AUTH` is True.
    - Validate 401 for missing token.

- **Consistency with `/token`**
  - Current: Sets `refresh_token` cookie and returns it in the body.
  - Change: Remove `response.set_cookie` unless `USE_COOKIE_AUTH` is True to align with header-based flow.

## Proposed Changes

### app/api/v1/endpoints/auth.py

- Modified `/refresh-token`:

```python
@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using a valid refresh token from Authorization header."""
    refresh_token = await get_token_from_header(request)
    try:
        token_data = await verify_token(refresh_token, db, expected_type="refresh")
        db.add(RevokedToken(jti=token_data.jti, revoked_at=datetime.now(timezone.utc)))
        await db.commit()

        access_jti = str(uuid4())
        refresh_jti = str(uuid4())
        new_access_token = await create_access_token(token_data.user_id, token_data.scopes, access_jti, db)
        new_refresh_token = await create_refresh_token(token_data.user_id, token_data.scopes, refresh_jti, db)

        if settings.USE_COOKIE_AUTH:
            response.set_cookie(
                key="refresh_token",
                value=new_refresh_token,
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=60 * 60 * 24 * 30,
                path="/api/v1/auth/refresh-token"
            )

        return Token(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=60 * 60 * 24 * 8,
            refresh_token=new_refresh_token
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not refresh token")
```

- Modified `/token` (remove cookie unless USE_COOKIE_AUTH):

```python
@router.post("/token", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    # ... existing logic up to token creation ...
    access_token = await create_access_token(subject=str(user.id), scopes=scopes, jti=access_jti, db=db)
    refresh_token = await create_refresh_token(subject=str(user.id), scopes=scopes, jti=refresh_jti, db=db)

    if settings.USE_COOKIE_AUTH:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,
            path="/api/v1/auth/refresh-token"
        )

    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=60 * 60 * 24 * 8,
        refresh_token=refresh_token
    )
```

### app/core/auth.py

- Updated `get_token_from_header`:

```python
async def get_token_from_header(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    if settings.USE_COOKIE_AUTH:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            return refresh_token
    raise HTTPException(status_code=401, detail="Refresh token missing")
```

### app/core/config.py

- Add to Settings:

```python
USE_COOKIE_AUTH: bool = Field(default=False, description="Use cookie-based refresh token if true, else header")
```

### app/tests/unit/api/test_auth_endpoints.py

- Updated `test_refresh_token_success`:

```python
@pytest.mark.asyncio
async def test_refresh_token_success(mock_create_refresh, mock_create_access, mock_verify_token):
    user_id = str(uuid4())
    refresh_jti = str(uuid4())
    token_data = TokenData(user_id=UUID(user_id), jti=refresh_jti, scopes=["user"], type="refresh")
    mock_verify_token.return_value = token_data
    mock_create_access.return_value = "new.access.token"
    mock_create_refresh.return_value = "new.refresh.token"

    mock_db = AsyncMock()
    mock_response = MagicMock()
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "Bearer valid.refresh.token"
    mock_request.cookies.get.return_value = None

    with patch("app.core.config.settings.USE_COOKIE_AUTH", False):
        response = await refresh_token(response=mock_response, request=mock_request, db=mock_db)

    assert response.access_token == "new.access.token"
    assert response.refresh_token == "new.refresh.token"
    mock_verify_token.assert_called_once_with("valid.refresh.token", mock_db, expected_type="refresh")
    mock_db.add.assert_called_once()
```

- New test for header vs. cookie:

```python
@pytest.mark.asyncio
async def test_refresh_token_with_cookie(mock_create_refresh, mock_create_access, mock_verify_token):
    user_id = str(uuid4())
    refresh_jti = str(uuid4())
    token_data = TokenData(user_id=UUID(user_id), jti=refresh_jti, scopes=["user"], type="refresh")
    mock_verify_token.return_value = token_data
    mock_create_access.return_value = "new.access.token"
    mock_create_refresh.return_value = "new.refresh.token"

    mock_db = AsyncMock()
    mock_response = MagicMock()
    mock_request = MagicMock()
    mock_request.headers.get.return_value = None
    mock_request.cookies.get.return_value = "valid.refresh.token"

    with patch("app.core.config.settings.USE_COOKIE_AUTH", True):
        response = await refresh_token(response=mock_response, request=mock_request, db=mock_db)

    assert response.refresh_token == "new.refresh.token"
    mock_response.set_cookie.assert_called_once()
```

## Impact

- `/token`: No longer sets cookie by default, reducing frontend-backend mismatch.
- `/refresh-token`: Accepts header input, fully compatible with NextAuth.
- **Security**: Refresh token in header/body is less secure than HttpOnly cookie; mitigated by rotation and short-lived tokens.
- **Backward Compatibility**: `USE_COOKIE_AUTH` preserves old behavior if needed.

## Risks

- **Breaking Changes**: Existing clients using cookie-based refresh will fail unless `USE_COOKIE_AUTH` is enabled.
- **Security Trade-off**: Refresh token exposed in header/body; consider shortening `REFRESH_TOKEN_EXPIRE_DAYS` (e.g., 7 days).
- **Testing Gaps**: Incomplete test coverage for edge cases (e.g., malformed headers).

## Validation Plan

- **Unit Tests**: Run updated `test_auth_endpoints.py` to verify header-based refresh and fallback behavior.
- **Integration Test**: Use NextAuth with:

```typescript
async jwt({ token, user }) {
  if (user) {
    token.accessToken = user.accessToken;
    token.refreshToken = user.refreshToken;
    token.accessTokenExpires = Date.now() + 8 * 24 * 60 * 60 * 1000;
  }
  if (Date.now() >= token.accessTokenExpires) {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/refresh-token`,
      {},
      { headers: { Authorization: `Bearer ${token.refreshToken}` } }
    );
    token.accessToken = response.data.access_token;
    token.refreshToken = response.data.refresh_token;
    token.accessTokenExpires = Date.now() + response.data.expires_in * 1000;
  }
  return token;
}
```

- **Manual Test**: Log in, wait for token expiration, verify refresh succeeds.

## Timeline

- **Development**: 1-2 days (code changes, testing).
- **Review**: 1 day.
- **Deployment**: Post-Phase 2 (March 14, 2025).
