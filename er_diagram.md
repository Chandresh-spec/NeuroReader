# Database Entity-Relationship Diagram

This diagram outlines the core data models for the application, specifically focusing on Users, their uploaded publications (Books/Files), and their associated reading progress data.

```mermaid
erDiagram
    USER {
        int id PK
        string email UK
        string full_name
        string password
        datetime last_login
        boolean is_active
        boolean is_staff
    }
    
    USER_FILE {
        int id PK
        int user_id FK
        string title
        string file_path
        string file_type "PDF, TXT, MD, HTML, RTF"
        int size_bytes
        datetime uploaded_at
    }
    
    USER_READING_DATA {
        int id PK
        int user_id FK
        int file_id FK
        float progress "0-100%"
        int pdf_page
        boolean bookmarked
        json highlights
        json notes
        datetime updated_at
    }

    USER ||--o{ USER_FILE : "uploads / owns"
    USER ||--o{ USER_READING_DATA : "has reading state for"
    USER_FILE ||--o{ USER_READING_DATA : "is read with"
```
