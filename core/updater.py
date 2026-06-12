"""
  Автоматическое обновление отключено согласно правилам площадки (п. 1.8).
  Новые версии публикуются на странице релизов:
  https://github.com/FTPLabs/FMailSender/releases
  """


  def check_for_updates(*args, **kwargs):
      return None


  def apply_update_windows(*args, **kwargs):
      return False


  def is_newer(*args, **kwargs):
      return False
  