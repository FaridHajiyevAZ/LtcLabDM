# After-Sales & Warranty Activation Platform — Architecture

## 1. High-Level System Architecture

```
                         ┌─────────────────────────┐
                         │     Load Balancer /      │
                         │     Reverse Proxy        │
                         │     (Nginx / Fly.io)     │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │    Flask Application      │
                         │    (Gunicorn WSGI)        │
                         │                           │
                         │  ┌─────────────────────┐  │
                         │  │  Auth Module         │  │
                         │  │  (JWT + Sessions)    │  │
                         │  ├─────────────────────┤  │
                         │  │  Customer Portal     │  │
                         │  │  (Views + API)       │  │
                         │  ├─────────────────────┤  │
                         │  │  Admin Dashboard     │  │
                         │  │  (Views + API)       │  │
                         │  ├─────────────────────┤  │
                         │  │  File Upload Service │  │
                         │  │  (Local / S3)        │  │
                         │  └─────────────────────┘  │
                         └──┬──────────┬─────────┬───┘
                            │          │         │
               ┌────────────▼──┐  ┌────▼────┐  ┌─▼──────────────┐
               │  PostgreSQL   │  │  Redis  │  │  File Storage  │
               │  (Primary DB) │  │  (OTP   │  │  (Local/S3)    │
               │               │  │  Cache) │  │                │
               └───────────────┘  └─────────┘  └────────────────┘
```

## 2. Tech Stack

| Layer          | Technology             | Reasoning                                              |
|----------------|------------------------|---------------------------------------------------------|
| Backend        | Flask 3.x + Python 3.11 | Already in use; lightweight, extensible                |
| ORM            | SQLAlchemy + Alembic   | Mature ORM with migration support                      |
| Database       | PostgreSQL             | ACID compliance, JSON support, production-grade         |
| Cache/OTP      | Redis (optional)       | Fast ephemeral storage for OTP codes; falls back to DB  |
| Auth           | Flask-Login + JWT      | Session-based for web, JWT for API consumers            |
| Password Hash  | Werkzeug (scrypt)      | Built into Flask, secure by default                     |
| File Storage   | Local disk / S3        | Configurable; local for dev, S3 for production          |
| Email          | Flask-Mail + SMTP      | Transactional email for OTP, confirmations              |
| Frontend       | Jinja2 + Bootstrap 5   | Server-rendered, fast, accessible                       |
| Deployment     | Docker + Fly.io        | Existing pipeline, minimal changes                      |
| CI/CD          | GitHub Actions         | Existing pipeline                                       |
| Testing        | pytest + coverage      | Standard Python testing                                 |

## 3. Database Schema

### Entity Relationship Diagram

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   User       │────<│ ProductRegistra- │────>│ MattressModel     │
│              │     │ tion             │     │                   │
│ id           │     │                  │     │ id                │
│ email        │     │ id               │     │ name              │
│ phone        │     │ user_id (FK)     │     │ warranty_months   │
│ password_hash│     │ model_id (FK)    │     │ description       │
│ role         │     │ purchase_source  │     │ is_active         │
│ is_verified  │     │ purchase_date    │     └───────────────────┘
│ created_at   │     │ warranty_status  │
│ updated_at   │     │ warranty_start   │     ┌───────────────────┐
└──────┬───────┘     │ warranty_end     │     │ RegistrationPhoto │
       │             │ serial_number    │     │                   │
       │             │ undamaged_conf   │     │ id                │
       │             │ accuracy_conf    │     │ registration_id   │
       │             │ admin_notes      │     │ photo_type        │
       │             │ reviewed_by      │     │ file_path         │
       │             │ created_at       │     │ original_filename │
       │             └────────┬─────────┘     │ file_hash         │
       │                      │               │ uploaded_at       │
       │                      └──────────────>└───────────────────┘
       │
       │             ┌──────────────────┐     ┌───────────────────┐
       └────────────<│ SupportTicket    │────<│ TicketMessage     │
                     │                  │     │                   │
                     │ id               │     │ id                │
                     │ user_id (FK)     │     │ ticket_id (FK)    │
                     │ registration_id  │     │ sender_id (FK)    │
                     │ subject          │     │ body              │
                     │ status           │     │ created_at        │
                     │ priority         │     └───────────────────┘
                     │ category         │
                     │ created_at       │     ┌───────────────────┐
                     │ updated_at       │────<│ TicketAttachment  │
                     └──────────────────┘     │                   │
                                              │ id                │
                     ┌──────────────────┐     │ message_id (FK)   │
                     │ OTPCode          │     │ file_path         │
                     │                  │     │ original_filename │
                     │ id               │     │ uploaded_at       │
                     │ user_id (FK)     │     └───────────────────┘
                     │ code             │
                     │ purpose          │     ┌───────────────────┐
                     │ expires_at       │     │ AuditLog          │
                     │ is_used          │     │                   │
                     └──────────────────┘     │ id                │
                                              │ user_id           │
                                              │ action            │
                                              │ entity_type       │
                                              │ entity_id         │
                                              │ details (JSON)    │
                                              │ ip_address        │
                                              │ created_at        │
                                              └───────────────────┘
```

## 4. API Endpoint Structure

### Authentication
| Method | Endpoint                    | Description                     | Auth     |
|--------|-----------------------------|---------------------------------|----------|
| POST   | /auth/register              | Register new customer           | Public   |
| POST   | /auth/login                 | Login with email/phone + pass   | Public   |
| POST   | /auth/logout                | End session                     | Customer |
| POST   | /auth/verify-email          | Verify email with token         | Public   |
| POST   | /auth/send-otp              | Send OTP to phone/email         | Public   |
| POST   | /auth/verify-otp            | Verify OTP code                 | Public   |
| POST   | /auth/forgot-password       | Initiate password reset         | Public   |
| POST   | /auth/reset-password        | Reset password with token       | Public   |

### Customer Portal
| Method | Endpoint                               | Description                       | Auth     |
|--------|----------------------------------------|-----------------------------------|----------|
| GET    | /dashboard                             | Customer dashboard                | Customer |
| GET    | /profile                               | View profile                      | Customer |
| POST   | /profile                               | Update profile                    | Customer |
| GET    | /products/register                     | Product registration form         | Customer |
| POST   | /products/register                     | Submit product registration       | Customer |
| GET    | /products                              | List registered products          | Customer |
| GET    | /products/<id>                         | View product + warranty details   | Customer |
| POST   | /products/<id>/photos                  | Upload additional photos          | Customer |
| GET    | /support                               | List support tickets              | Customer |
| GET    | /support/new                           | New ticket form                   | Customer |
| POST   | /support/new                           | Create support ticket             | Customer |
| GET    | /support/<id>                          | View ticket thread                | Customer |
| POST   | /support/<id>/reply                    | Reply to ticket                   | Customer |

### Admin Panel
| Method | Endpoint                               | Description                       | Auth     |
|--------|----------------------------------------|-----------------------------------|----------|
| GET    | /admin/dashboard                       | Admin overview                    | Admin    |
| GET    | /admin/registrations                   | All product registrations         | Admin    |
| GET    | /admin/registrations/<id>              | Registration detail               | Admin    |
| POST   | /admin/registrations/<id>/approve      | Approve registration              | Admin    |
| POST   | /admin/registrations/<id>/reject       | Reject registration               | Admin    |
| POST   | /admin/registrations/<id>/request-info | Request additional info            | Admin    |
| GET    | /admin/tickets                         | All support tickets               | Admin    |
| GET    | /admin/tickets/<id>                    | View ticket                       | Admin    |
| POST   | /admin/tickets/<id>/reply              | Reply to ticket                   | Admin    |
| POST   | /admin/tickets/<id>/status             | Update ticket status              | Admin    |
| GET    | /admin/customers                       | Customer list                     | Admin    |
| GET    | /admin/customers/<id>                  | Customer detail                   | Admin    |
| GET    | /admin/models                          | Mattress model management         | Admin    |
| POST   | /admin/models                          | Add mattress model                | Admin    |
| GET    | /admin/fraud-alerts                    | Fraud detection view              | Admin    |
| GET    | /admin/audit-log                       | Audit trail                       | Admin    |

## 5. Authentication & Security Flow

### Registration Flow
```
Customer → Register (email/phone + password)
    → Validate input (format, uniqueness)
    → Hash password (scrypt via Werkzeug)
    → Store user (is_verified=False)
    → Send verification email/OTP
    → Customer verifies → is_verified=True
    → Redirect to login
```

### Login Flow
```
Customer → Login (email or phone + password)
    → Check credentials
    → Verify account is_verified=True
    → Create Flask session (session-based auth)
    → Set session["user_id"] and session["role"]
    → Redirect to dashboard
```

### RBAC Enforcement
```python
# Decorator-based access control
@login_required          # Any authenticated user
@customer_required       # Only role="customer"
@admin_required          # Only role="admin"
```

### Security Measures
- CSRF tokens on all POST forms (Flask-WTF)
- Password hashing with scrypt (Werkzeug)
- OTP codes expire after 10 minutes
- Rate limiting on auth endpoints
- File upload validation (type, size, dimensions)
- Duplicate detection via file content hashing (SHA-256)
- SQL injection prevention (SQLAlchemy parameterized queries)
- XSS prevention (Jinja2 auto-escaping)
- Secure session cookies (HttpOnly, SameSite, Secure in production)

## 6. Key Edge Cases & Validation Rules

### Product Registration
- **Duplicate serial number**: Reject if same serial already registered
- **Duplicate invoice hash**: Flag for admin review (fraud indicator)
- **Future purchase date**: Reject; purchase date must be <= today
- **Purchase date too old**: Warn if > 30 days ago; flag for review if > 90 days
- **File upload limits**: Max 5MB per image, JPEG/PNG only
- **Warranty calculation**: Start date = purchase date; end date = start + model warranty months

### Authentication
- **Email normalization**: Lowercase, strip whitespace
- **Phone normalization**: Strip non-digits, validate format
- **OTP brute force**: Lock after 5 failed attempts for 30 minutes
- **Password requirements**: Minimum 8 characters, at least 1 letter + 1 digit
- **Session timeout**: 30 minutes of inactivity

### Support Tickets
- **Orphan prevention**: Ticket must reference a registered product
- **Status transitions**: Open → In Progress → Resolved (no backwards)
- **Attachment limits**: Max 3 attachments per message, 5MB each

### GDPR Compliance
- **Data export**: Customer can request all their data as JSON
- **Data deletion**: Customer can request account deletion
- **Consent tracking**: Store consent timestamps for T&C acceptance
- **Audit log**: Track all data access and modifications
- **Retention policy**: Auto-archive data after warranty expiry + 2 years
