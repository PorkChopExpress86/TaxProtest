"""Attempt partial DBF recovery from corrupt Parcels.zip

This script tries to extract the beginning of the corrupt Parcels.dbf file
to see if any records can be salvaged before the corruption point.
"""
import zipfile
import struct
from pathlib import Path

def analyze_dbf_header(dbf_bytes: bytes) -> dict:
    """Parse DBF header to understand structure."""
    if len(dbf_bytes) < 32:
        return {"error": "Too short for DBF header"}
    
    try:
        # DBF header structure
        version = dbf_bytes[0]
        year = dbf_bytes[1] + 1900
        month = dbf_bytes[2]  
        day = dbf_bytes[3]
        num_records = struct.unpack('<I', dbf_bytes[4:8])[0]
        header_length = struct.unpack('<H', dbf_bytes[8:10])[0] 
        record_length = struct.unpack('<H', dbf_bytes[10:12])[0]
        
        return {
            "version": version,
            "last_update": f"{year:04d}-{month:02d}-{day:02d}",
            "num_records": num_records,
            "header_length": header_length,
            "record_length": record_length,
            "calculated_file_size": header_length + (num_records * record_length) + 1
        }
    except Exception as e:
        return {"error": f"Header parse failed: {e}"}

def attempt_partial_dbf_extract():
    """Try to extract partial DBF data ignoring CRC."""
    parcels_zip = Path("downloads_test/Parcels.zip")
    
    if not parcels_zip.exists():
        print("❌ Parcels.zip not found")
        return
        
    try:
        with zipfile.ZipFile(parcels_zip, 'r') as zf:
            # Try to read the DBF member directly (ignoring CRC)
            info = zf.getinfo("HCAD_PDATA/Parcels/Parcels.dbf")
            print(f"DBF info: {info.file_size:,} bytes compressed, {info.compress_size:,} bytes on disk")
            
            # Read raw compressed data
            with zf.open("HCAD_PDATA/Parcels/Parcels.dbf") as f:
                # Try to read in chunks, stopping at first error
                chunk_size = 64 * 1024  # 64KB chunks
                chunks = []
                total_read = 0
                
                while total_read < info.file_size:
                    try:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        total_read += len(chunk)
                        if len(chunks) % 10 == 0:
                            print(f"  Read {total_read:,} bytes so far...")
                    except Exception as e:
                        print(f"  Read stopped at {total_read:,} bytes due to: {e}")
                        break
                
                if chunks:
                    partial_dbf = b''.join(chunks)
                    print(f"✅ Recovered {len(partial_dbf):,} bytes of DBF data")
                    
                    # Analyze header
                    header_info = analyze_dbf_header(partial_dbf)
                    print("DBF Header Analysis:")
                    for key, value in header_info.items():
                        print(f"  {key}: {value}")
                    
                    # Save partial DBF
                    output_path = Path("extracted_test/partial_parcels.dbf")
                    output_path.parent.mkdir(exist_ok=True)
                    with open(output_path, 'wb') as out_f:
                        out_f.write(partial_dbf)
                    print(f"💾 Saved partial DBF to {output_path}")
                    
                    return len(partial_dbf)
                else:
                    print("❌ No data recovered")
                    return 0
                    
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return 0

if __name__ == "__main__":
    print("🔧 Attempting partial DBF recovery...")
    bytes_recovered = attempt_partial_dbf_extract()
    
    if bytes_recovered > 0:
        print(f"\n📊 Summary: Recovered {bytes_recovered:,} bytes")
        print("Note: Partial DBF may be unusable due to structural damage.")
        print("The 2024 October archive provides a complete working alternative.")
    else:
        print("\n❌ No usable data recovered from corrupt DBF.")
