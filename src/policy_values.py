# Valid values from POLICY.md section 3. Other files import these,
# so the policy is written down in exactly one place in the code.

VALID_CLEARANCES = {0, 1, 2, 3}

# Departments a user can belong to ("ALL" is never valid for a user).
USER_DEPARTMENTS = {"HR", "Finance", "Engineering", "Legal", "Executive"}

# Departments a document can belong to: the same list plus "ALL".
DOCUMENT_DEPARTMENTS = USER_DEPARTMENTS | {"ALL"}

VALID_ROLES = {"Intern", "Engineer", "HR Manager", "Finance Head", "Legal Counsel", "CEO"}