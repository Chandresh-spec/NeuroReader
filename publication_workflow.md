# Publication Workflow Diagram

This diagram maps out how a user can upload their publications (books/files), ensuring they are securely tied to their account and that only the owner can read, edit, or delete them.

```mermaid
stateDiagram-v2
    direction TB
    
    [*] --> Dashboard : User Logs In
    
    state Dashboard {
        Upload : Upload New Book
        View_Library : View Personal Library
    }
    
    Upload --> Backend_Validation : Select File (PDF/TXT/MD)
    
    Backend_Validation --> Save_File : Valid Format & Size
    Backend_Validation --> Upload_Error : Invalid
    
    Save_File --> Create_UserFile_Record : Store on Disk (media/user_files/<id>/)
    Create_UserFile_Record --> Library_Updated : Link to User ID
    
    Library_Updated --> View_Library
    
    View_Library --> Reading_Interface : Click Book
    View_Library --> Delete_Prompt : Click Delete
    
    state Reading_Interface {
        Read : Read Content
        Highlight : Add Highlights
        Notes : Edit Notes
    }
    
    Reading_Interface --> Save_Progress : Auto-save every N seconds
    Save_Progress --> View_Library : Exit Reader
    
    Delete_Prompt --> Confirm_Delete : Confirm
    Delete_Prompt --> View_Library : Cancel
    
    Confirm_Delete --> Check_Ownership : API Request
    
    Check_Ownership --> Remove_From_DB : User = Owner (Authorized)
    Check_Ownership --> Deny_Access : User != Owner (Unauthorized 403)
    
    Remove_From_DB --> Delete_File_From_Disk
    Delete_File_From_Disk --> Library_Updated
```
