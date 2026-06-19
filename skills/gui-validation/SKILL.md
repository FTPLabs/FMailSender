# GUI Validation Skill

  ## Module: `core/gui_validator.py`
  Import: `from core.gui_validator import validate_account_form, validate_email`

  ### Functions
  | Function | Arguments | Returns |
  |---|---|---|
  | `validate_email(value)` | str | (bool, reason_str) |
  | `validate_smtp_host(value)` | str | (bool, reason_str) |
  | `validate_port(value)` | int\|str | (bool, reason_str) |
  | `validate_password(value, min_len=4)` | str | (bool, reason_str) |
  | `validate_account_form(email, password, host, port)` | strs | List[FieldError] |

  ### Usage in AccountDialog._validate_and_accept
  ```python
  from core.gui_validator import validate_account_form
  errors = validate_account_form(
      self.email_edit.text(),
      self.password_edit.text(),
      self.host_edit.text(),
      self.port_spin.value(),
  )
  if errors:
      QMessageBox.warning(self, "Ошибка", "\n".join(str(e) for e in errors))
      return
  self.accept()
  ```
  