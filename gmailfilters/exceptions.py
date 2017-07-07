class GmailFilterError(Exception):
    pass

class NoConfigurationFile(GmailFilterError):
    pass

class NoSuchAccount(GmailFilterError):
    pass

class NoMatchingMessages(GmailFilterError):
    pass

class NoMatchingFolders(GmailFilterError):
    pass

class InvalidOptions(GmailFilterError):
    pass
