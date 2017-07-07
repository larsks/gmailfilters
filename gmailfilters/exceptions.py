class GmailFilterError(Exception):
    pass

class NoConfigurationFile(GmailFilterError):
    pass

class NoSuchAccount(GmailFilterError):
    pass
