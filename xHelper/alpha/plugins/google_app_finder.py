class GoogleAppFinderPlugin:
    """
    Плагин для xHelper: поиск всех приложений с 'google' в имени пакета.
    """

    def __init__(self, adb):
        """
        adb: объект для работы с ADB, предоставляемый xHelper
        """
        self.adb = adb

    def run(self):
        try:
            # Получаем список всех установленных пакетов
            output = self.adb.shell("pm list packages")
            packages = output.splitlines()

            # Фильтруем пакеты с 'google' в имени
            google_packages = [p.replace("package:", "") for p in packages if "google" in p.lower()]

            if google_packages:
                print("Найденные приложения с 'google' в пакете:")
                for pkg in google_packages:
                    print(f" - {pkg}")
            else:
                print("Приложения с 'google' не найдены.")

        except Exception as e:
            print(f"Ошибка при выполнении плагина: {e}")