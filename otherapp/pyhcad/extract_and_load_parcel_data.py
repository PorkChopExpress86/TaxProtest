import os
from zipfile import ZipFile as zf

import geopandas as gpd


def unzip_parcel_data(src, dst) -> None:
    for root, dirs, files in os.walk(src):
        for name in files:
            if name == "Parcels.zip":
                file_path = os.path.join(root, name)
                with zf(file_path, "r") as zFile:
                    zFile.extractall(dst)


def extract_parcel_data(src, dst) -> None:
    gdf = gpd.read_file(src)

    if gdf.crs is None:
        raise ValueError("The shapefile does not have a CRS defined.")

    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    # Validate geometries and filter out invalid ones
    gdf = gdf[gdf.geometry.is_valid]

    gdf = gdf[gdf.geometry.apply(has_sufficient_points)]

    # Extract latitude and longitude from geometry
    # Use the centroid of the geometry
    gdf["latitude"] = gdf.geometry.centroid.y
    gdf["longitude"] = gdf.geometry.centroid.x

    # Save the data table with lat/lon to a CSV file
    gdf.drop(columns=["geometry"]).to_csv(dst, index=False)


def has_sufficient_points(geometry):
    # Handle Polygon geometries
    if geometry.geom_type == "Polygon":
        return len(geometry.exterior.coords) >= 4
    # Handle MultiPolygon geometries
    elif geometry.geom_type == "MultiPolygon":
        return all(len(polygon.exterior.coords) >= 4 for polygon in geometry.geoms)
    # Skip other geometry types
    return False


if __name__ == "__main__":
    unzip_parcel_data("Zips", "Data")
    extract_parcel_data("Data/Parcels.shp", "Data/parcels.csv")
