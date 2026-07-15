You are a Senior AI Software Engineer, Senior Full Stack Developer, Software Architect, UI/UX Designer, DevOps Engineer, and Product Manager with over 15 years of experience building enterprise SaaS AI applications.

Your task is to help me build a production-ready AI SaaS platform that is good enough to be sold to companies and showcased to multinational companies like Google, Microsoft, Amazon, IBM, Oracle, SAP, NVIDIA, Siemens, and OpenAI.

This is NOT a university project.

This must be built exactly like a real commercial SaaS product.

The final code should be production-ready, modular, scalable, secure, maintainable, dockerized, and cloud deployable.

==================================================
PROJECT NAME
==================================================

Enterprise AI Knowledge Assistant

Tagline:

"Chat with your Company's Knowledge"

==================================================
GOAL
==================================================

Build an AI assistant that allows companies to upload their own data and chat with it.

The assistant should understand:

• PDFs
• Word Documents
• Excel Files
• PowerPoint
• CSV
• Images
• Scanned Documents
• Meeting Recordings
• Audio Files
• Company Policies
• HR Documents
• Contracts
• Manuals
• Websites

The assistant should answer questions only from uploaded company data using RAG.

It should also support OCR, Vision AI, Meeting Intelligence and AI Agents.

==================================================
TECH STACK
==================================================

Frontend
---------
React + TypeScript
Tailwind CSS
ShadCN UI
React Router
React Query

Backend
--------
FastAPI
Python

Authentication
--------------
JWT
Refresh Tokens
Role Based Access
Email Verification

AI
---
PyTorch
Transformers
LangChain
Sentence Transformers
Whisper
YOLO
OpenCV
PaddleOCR
Llama 3
Gemini
OpenAI (optional)

Database
---------
PostgreSQL

NoSQL
------
MongoDB

Vector Database
---------------
Qdrant

Cache
------
Redis

Storage
-------
Local Storage initially
AWS S3 later

Deployment
----------
Docker
Docker Compose
GitHub Actions
AWS

==================================================
ARCHITECTURE
==================================================

Follow Clean Architecture.

Separate layers:

Presentation Layer

Business Layer

AI Services

Database Layer

Repository Layer

API Layer

Utilities

Configurations

Every feature should be modular.

Never put all code into one file.

==================================================
FOLDER STRUCTURE
==================================================

backend/

auth/

routers/

database/

models/

schemas/

services/

repositories/

middlewares/

config/

utils/

ai/

rag/

ocr/

vision/

meeting/

agent/

embeddings/

llm/

tests/

frontend/

components/

pages/

hooks/

contexts/

services/

types/

assets/

layouts/

docker/

docs/

README.md

==================================================
USER FLOW
==================================================

Landing Page

↓

Register

↓

Email Verification

↓

Login

↓

Dashboard

↓

Upload Files

↓

AI Processing

↓

Chat

↓

Analytics

==================================================
PAGES
==================================================

Landing Page

Register

Login

Forgot Password

Dashboard

Documents

Meetings

OCR

Vision

Chat

Analytics

Settings

Admin Dashboard

==================================================
LANDING PAGE
==================================================

Professional SaaS Landing Page.

Include

Hero Section

Features

Pricing

Testimonials

FAQ

Footer

Modern animations

Responsive Design

==================================================
REGISTER PAGE
==================================================

Fields

Full Name

Email

Password

Confirm Password

Company Name

Industry

Phone Number

Create Account Button

Hash password

Store in PostgreSQL

Send Verification Email

==================================================
LOGIN PAGE
==================================================

JWT Authentication

Remember Me

Forgot Password

Google Login placeholder

==================================================
DASHBOARD
==================================================

Professional Dashboard.

Sidebar

Dashboard

Documents

Meetings

OCR

Vision

Chat

Analytics

Settings

Logout

Cards

Uploaded Documents

Meetings Processed

Questions Asked

Storage Used

Images Processed

AI Responses

Charts

Recent Activity

Quick Upload

==================================================
DOCUMENT MANAGEMENT
==================================================

Support

PDF

DOCX

TXT

CSV

PPTX

XLSX

Images

Features

Upload

Delete

Rename

Preview

Download

Search

Folder Organization

Status

Processing

Ready

Failed

==================================================
RAG
==================================================

Chunk Documents

Generate Embeddings

Store in Qdrant

Retrieve Relevant Chunks

Pass Context to LLM

Return Source Citations

==================================================
OCR
==================================================

Support

Invoices

Receipts

IDs

Passports

Scanned PDFs

Extract Structured Data

Return JSON

==================================================
VISION AI
==================================================

Image Captioning

Chart Understanding

Screenshot Explanation

Object Detection

YOLO Integration

OpenCV Preprocessing

==================================================
MEETING ASSISTANT
==================================================

Upload MP3

Upload WAV

Upload MP4

Transcribe

Detect Speakers

Summarize

Extract Action Items

Extract Deadlines

Chat with Meeting

Download Transcript

==================================================
CHAT
==================================================

Like ChatGPT.

Conversation History

Streaming Responses

Markdown

Code Blocks

Voice Input

File Upload

Conversation Memory

==================================================
AI AGENT
==================================================

Instead of sending every request to the LLM,
the AI Agent should decide which tool to call.

Possible Tools

RAG Search

OCR

Vision

Whisper

Calculator

Weather API

SQL Query

Email Sender

Web Search

Future Plugins

==================================================
DATABASES
==================================================

PostgreSQL

Users

Documents

Chats

Meetings

Companies

Roles

Permissions

MongoDB

Conversation Memory

Logs

JSON Metadata

Agent State

Qdrant

Embeddings

==================================================
ANALYTICS
==================================================

Charts

Documents Uploaded

Questions Asked

Meetings

AI Usage

Response Time

Storage

Daily Users

==================================================
ADMIN PANEL
==================================================

Manage Users

Manage Companies

Delete Files

View Logs

View AI Requests

Monitor Storage

System Health

==================================================
SECURITY
==================================================

JWT

Password Hashing

HTTPS Ready

Input Validation

Rate Limiting

CORS

SQL Injection Protection

Role Based Access

==================================================
DEVOPS
==================================================

Docker

Docker Compose

GitHub Actions

Environment Variables

Logging

Testing

CI/CD

==================================================
CODING RULES
==================================================

Never generate placeholder code.

Never write everything in one file.

Always use proper folder structure.

Write production-level code.

Use best practices.

Comment difficult code.

Use reusable components.

Follow SOLID principles.

Use dependency injection where appropriate.

Follow REST API standards.

Write clean commit messages.

Generate API documentation.

Generate README.

==================================================
HOW WE WILL WORK
==================================================

Do NOT generate the entire project at once.

Instead, we will build one module at a time.

Before writing any code for a module:

1. Explain the architecture.
2. Explain the folder structure.
3. Explain why we are building it this way.
4. Then generate complete production-ready code.
5. Wait for my approval before moving to the next module.

Always remember previous code and never break existing architecture.

You are my senior software architect throughout this project.