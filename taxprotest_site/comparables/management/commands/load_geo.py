from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Load geographic parcel data into the project's property_geo table by delegating to load_geo_data.py"

    def handle(self, *args, **options):
        # Import the project's loader and run it. We import locally to avoid import-time side effects.
        try:
            import load_geo_data
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to import load_geo_data: {e}"))
            raise

        try:
            load_geo_data.load_geo_data()
            self.stdout.write(self.style.SUCCESS("load_geo completed"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"load_geo failed: {e}"))
            raise
