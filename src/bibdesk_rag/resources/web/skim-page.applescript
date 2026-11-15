on run argv
    set targetPath to item 1 of argv
    set targetPage to (item 2 of argv) as integer
    set targetFile to POSIX file targetPath
    tell application "Skim"
        open targetFile
        set targetDocuments to get documents whose path is targetPath
        if (count of targetDocuments) is 0 then error "Target PDF is not open"
        set targetDocument to contents of item 1 of targetDocuments
        if targetPage > (count of pages of targetDocument) then error "Page is outside the PDF"
        go targetDocument to (page targetPage of targetDocument)
        set targetWindows to get windows whose document is targetDocument
        if (count of targetWindows) > 0 then set index of item 1 of targetWindows to 1
        activate
    end tell
end run
