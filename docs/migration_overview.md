# Migration Roadmap Overview

This document outlines the recommended roadmap for our system refactoring initiative. The migration is divided into three primary domains, each containing specific PRDs that should be accomplished sequentially.

## 1. Architectural Changes

### 1.1 Migrate from Flask to FastAPI - Completed

- Convert Flask's synchronous routes to FastAPI's asynchronous APIRouters
- Implement dependency injection patterns
- Integrate Jinja2 templates with FastAPI

### 1.2 Make Database Sessions Asynchronous - Completed

- Transition to SQLAlchemy AsyncSessions
- Implement asyncpg driver integration
- Update data access patterns for async operations

### 1.3 Transition Server from Gunicorn to ASGI - Completed

- Replace WSGI server (Gunicorn) with ASGI server
- Options include Uvicorn or Hypercorn
- Ensure full async operation support

## 2. Authentication Changes

### 2.1 Implement OAuth2/JWT Login Flow - Completed

- Develop new authentication endpoints
- Implement JWT token generation
- Integrate OAuth2 authentication flow

### 2.2 Secure Endpoints Using Dependency Injection - Completed

- Develop `get_current_user` dependency
- Implement JWT validation and parsing
- Secure API endpoints throughout application

### 2.3 Token Lifecycle Management - Completed

- Define token refresh strategy
- Implement revocation mechanisms
- Establish key rotation protocols

## 3. Migrate services to use async and new data models

### 3.1 Update data models to use async and new data models - Completed

- Update model initialization to use async
- Update model methods to use async
- Update model tests to use async
- Add new data models

### 3.2 Migrate Logbook sync services to use async and new data models - Completed

- Update service initialization to use async
- Update service methods to use async
- Update service tests to use async
- Test all logbook services

# Implementation Plan: Continuing the Migration to Next.js/FastAPI

This implementation plan outlines the steps to complete the migration of the Send Sage application to a Next.js frontend and FastAPI backend, building on the existing backend authentication routes hosted on Render and aligning with the recommended solution: NextAuth for login/logout and Axios interceptors for client-side token refresh. The plan addresses the pending tasks from the migration roadmap, integrates the frontend with the backend, and ensures compatibility with the `get_current_user` dependency.

## Key Points

- **Current State**: Backend auth routes (`/token`, `/refresh-token`, `/logout`, etc.) are operational on Render, with `get_current_user` validating access tokens. Architectural and authentication changes are complete, and some service migrations (data models, Logbook sync) are done.
- **Pending Tasks**: Migrate Chat, User, Payment, and Data services to async and new data models, and implement the Next.js frontend.
- **Recommended Solution**: NextAuth manages login/logout, Axios interceptors handle token refresh client-side, ensuring valid access tokens for `get_current_user`.
- **Surprising Aspect**: The refresh token’s HttpOnly cookie requires client-side handling due to cross-domain separation, but this aligns with the backend design without necessitating major changes.

## Objectives

- Complete the migration of backend services to async operations and new data models.
- Implement a Next.js frontend with NextAuth for authentication and Axios for API interactions, integrating with the FastAPI backend on Render.
- Ensure seamless interaction with the `get_current_user` dependency and existing auth routes.
- Test and deploy the updated system, maintaining security and performance.

## Phases and Tasks

### Phase 1: Backend Service Migration Completion

**Goal**: Finalize the migration of remaining services to async operations and new data models, ensuring backend readiness for frontend integration.

#### 1. Migrate Chat Services (3.3)

- **Tasks**:
  - Update service initialization to use async (e.g., `async def __init__` with `AsyncSession`).
  - Convert service methods to async (e.g., `async def get_messages(self, user_id)` using `await db.execute`).
  - Update tests to use async (e.g., `pytest-asyncio` with `async def test_get_messages()`).
  - Test all chat services locally with a test database.
- **Output**: Fully async Chat services, tested and functional.
- **Duration**: 2-3 days.

#### 2. Create and Test User Services (3.4)

- **Tasks**:
  - Create async initialization (e.g., `UserService` class with `async def __init__(self, db: AsyncSession)`).
  - Implement async methods (e.g., `async def get_user(self, user_id)`).
  - Write async tests (e.g., `async def test_get_user()`).
  - Test all user operations (CRUD) locally.
- **Output**: New User services, async-ready and tested.
- **Duration**: 2-3 days.

#### 3. Create and Test Payment Services (3.5)

- **Tasks**:
  - Create async initialization (e.g., `PaymentService` with external API calls using `aiohttp`).
  - Implement async methods (e.g., `async def process_payment(self, amount)`).
  - Write async tests, mocking external APIs.
  - Test payment flows locally.
- **Output**: Async Payment services, tested for reliability.
- **Duration**: 3-4 days (due to external integration).

#### 4. Create and Test Data Services (3.6)

- **Tasks**:
  - Create async initialization (e.g., `DataService` with `AsyncSession`).
  - Implement async methods (e.g., `async def fetch_data(self, query)`).
  - Write async tests (e.g., `async def test_fetch_data()`).
  - Test data operations with large datasets locally.
- **Output**: Async Data services, tested for performance.
- **Duration**: 2-3 days.

#### 5. Deploy and Verify Backend Updates

- **Tasks**:
  - Deploy updated services to Render via Git push or CLI.
  - Test endpoints (e.g., `/chat`, `/users`, `/payments`, `/data`) via Postman or curl against Render URL.
  - Verify `get_current_user` works with updated services by sending authenticated requests.
- **Output**: Fully migrated backend on Render, all services async and operational.
- **Duration**: 1-2 days.

**Total Duration**: 10-15 days

---

### Phase 2: Next.js Frontend Setup and Integration

**Goal**: Implement the Next.js frontend with NextAuth and Axios, integrating with the FastAPI backend on Render.

#### 1. Set Up Next.js Project (4.1)

- **Tasks**:
  - Run `npx create-next-app@latest send-sage-frontend --typescript`.
  - Install dependencies: `npm install next-auth axios`.
  - Set up project structure: `pages/`, `lib/`, `components/`.
- **Output**: Basic Next.js project ready for development.
- **Duration**: 1 day.

#### 2. Configure Environment Variables (4.2)

- **Tasks**:
  - Create `.env.local`:
    NEXT_PUBLIC_API_URL=https://your-fastapi-app.onrender.com
    NEXTAUTH_URL=http://localhost:3000
    NEXTAUTH_SECRET=your-secret-here # Generate with openssl rand -base64 32
- Use variables in code (e.g., `process.env.NEXT_PUBLIC_API_URL`).
- **Output**: Configured environment for local dev and production.
- **Duration**: 1 hour.

#### 3. Ensure CORS on FastAPI Backend (4.3)

- **Tasks**:
- Add CORS middleware to FastAPI (if not already present):

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- Deploy to Render and test CORS with a frontend request.
- **Output**: Backend allows frontend requests, verified via browser dev tools.
- **Duration**: 1 day (including deployment).

#### 4. Integrate with FastAPI Backend (4.4)

- **Tasks**:
  - NextAuth Setup: Create pages/api/auth/[...nextauth].ts:

```typescript
import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

export default NextAuth({
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: { username: { type: "email" }, password: {} },
      async authorize(credentials) {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/token`, {
          method: "POST",
          body: new URLSearchParams(credentials),
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        })
        const data = await res.json()
        if (res.ok && data.access_token)
          return { accessToken: data.access_token }
        return null
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user?.accessToken) token.accessToken = user.accessToken
      return token
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken
      return session
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
})
```

- Axios Setup: Create lib/api.ts:

```typescript
import axios from "axios"

const api = axios.create({ baseURL: process.env.NEXT_PUBLIC_API_URL })

let isRefreshing = false
let failedQueue = []

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) =>
    error ? prom.reject(error) : prom.resolve(token)
  )
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) =>
          failedQueue.push({ resolve, reject })
        )
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return api(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL}/refresh-token`
        )
        const newAccessToken = data.access_token
        api.defaults.headers.Authorization = `Bearer ${newAccessToken}`
        processQueue(null, newAccessToken)
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        return api(originalRequest)
      } catch (err) {
        processQueue(err, null)
        return Promise.reject(err)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

export default api
```

- **Login Page** Create pages/login.tsx:

```typescript
import { signIn } from "next-auth/react"
import { useState } from "react"

export default function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()
    await signIn("credentials", {
      username: email,
      password,
      redirect: true,
      callbackUrl: "/",
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit">Login</button>
    </form>
  )
}
```

- Logout: Add logout button in components/Navbar.tsx:

```typescript
import { signOut, useSession } from "next-auth/react"

export default function Navbar() {
  const { data: session } = useSession()

  return (
    <nav>
      {session && (
        <button
          onClick={async () => {
            await fetch(`${process.env.NEXT_PUBLIC_API_URL}/logout`, {
              method: "POST",
              headers: { Authorization: `Bearer ${session.accessToken}` },
            })
            await signOut({ callbackUrl: "/login" })
          }}
        >
          Logout
        </button>
      )}
    </nav>
  )
}
```

- **Output**: Functional login/logout with NextAuth, Axios ready for API calls.
- **Duration**: 2-3 days.

#### 5. Update UI Components (4.5)

- **Tasks**:
  - Create pages/index.tsx to fetch user data:

```typescript
import { useSession } from "next-auth/react"
import api from "../lib/api"
import { useEffect, useState } from "react"

export default function Home() {
  const { data: session } = useSession()
  const [userData, setUserData] = useState(null)

  useEffect(() => {
    if (session) {
      api.get("/user-data").then((res) => setUserData(res.data))
    }
  }, [session])

  if (!session) return <p>Please login</p>
  return <div>{userData ? `Welcome, ${userData.email}` : "Loading..."}</div>
}
```

- Add components for Chat, User, Payment, Data services, fetching data via api.get("/endpoint").
- **Output**: UI reflecting backend services, authenticated via get_current_user.
- **Duration**: 3-4 days.

#### 6. Optimize Performance (4.6)

- **Tasks**:
  - Use getServerSideProps for initial data:

```typescript
import { getSession } from "next-auth/react"
import api from "../lib/api"

export async function getServerSideProps(context) {
  const session = await getSession(context)
  if (!session) return { redirect: { destination: "/login", permanent: false } }
  const { data } = await api.get("/user-data", {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  })
  return { props: { initialData: data } }
}
```

- Optimize images with Next.js <Image />.
- **Output**: Fast, responsive frontend.
- **Duration**: 2 days.

#### 7. Test the Frontend (4.7)

- **Tasks**:
  - Write unit tests with Jest (npm install --save-dev jest @testing-library/react):

```typescript
import { render, screen } from "@testing-library/react"
test("renders login", () => {
  render(<Login />)
  expect(screen.getByText("Login")).toBeInTheDocument()
})
```

- Integration tests with Cypress (npm install cypress --save-dev):

```typescript
it("logs in", () => {
  cy.visit("/login")
  cy.get("input[type=email]").type("test@example.com")
  cy.get("input[type=password]").type("password")
  cy.get("button").click()
  cy.url().should("eq", "http://localhost:3000/")
})
```

- Test against Render backend.
- **Output**: Fully tested frontend.
- **Duration**: 3-4 days.

**Total Duration**: 12-17 days

### Phase 3: Deployment and Validation

**Goal**: Deploy the frontend, validate the integrated system, and ensure production readiness.

#### 1. Deploy Frontend to Vercel

- **Tasks**:
  - Push to GitHub, connect to Vercel.
  - Set environment variables in Vercel dashboard.
  - Deploy and get production URL (e.g., https://your-frontend.vercel.app).
- **Output**: Live frontend on Vercel.
- **Duration**: 1 day.

#### 2. Update Backend CORS

- **Tasks**:
  - Add Vercel domain to CORS origins, redeploy to Render.
- **Output**: Backend accepts frontend requests.
- **Duration**: 1 day.

#### 3. End-to-End Validation

- **Tasks**:
  - Test login, refresh, logout, and service endpoints (Chat, User, Payment, Data).
    Verify get_current_user works with refreshed tokens.
    Monitor logs for errors.
- **Output**: Validated, production-ready system.
- **Duration**: 2-3 days.

**Total Duration**: 4-5 days

### Timeline and Resources

- **Total Duration**: 26-37 days (4-5 weeks)
- **Resources**:
  - Backend Developer: Phases 1, 3 (service migration, deployment).
  - Frontend Developer: Phase 2 (Next.js setup, UI).
  - Tester: Phases 2 (testing), 3 (validation).
  - Dependencies: Render account, Vercel account, GitHub repo.

**Milestones**

- Backend Services Complete: All services async, deployed to Render (Week 2).
- Frontend Functional: Next.js with auth and basic UI, tested locally (Week 4).
- System Deployed: Frontend on Vercel, integrated with backend, fully validated (Week 5).

**Risks and Mitigations**

- Service Migration Bugs: Test thoroughly locally before deployment.
- CORS Issues: Pre-validate CORS setup with local frontend.
- Refresh Token Failures: Ensure Axios interceptor handles errors gracefully (e.g., redirect to login on failure).

**Conclusion**

This plan completes the migration by finalizing backend services and implementing a Next.js frontend with NextAuth and Axios, leveraging the existing FastAPI auth routes on Render. The recommended solution ensures elegant integration with get_current_user, requiring no major backend changes beyond optional refinements (e.g., simplifying /token response). The phased approach balances speed and stability, delivering a modern, secure, and scalable system by mid-March 2025 (starting February 20, 2025).

**Key Citations**

- NextAuth.js documentation
- FastAPI documentation
- Axios interceptors guide
