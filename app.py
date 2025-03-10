import streamlit as st
import requests
import os
import re
import ffmpeg
from requests.exceptions import HTTPError
from pathlib import Path

# Default HTTP headers (from your cURL commands)
DEFAULT_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "priority": "u=1, i",
    "referer": "https://laharinagar.com/audios?type=messages&year=1967&month=SEPTEMBER",
    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
}

# Output directory
OUTPUT_DIR = "downloaded_audio"

def download_file(url, output_path, headers=None, cookies=None):
    """Download a file from a URL and save it to the specified path."""
    try:
        response = requests.get(url, headers=headers, cookies=cookies, stream=True)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        st.write(f"Downloaded: {output_path}")
        return True
    except HTTPError as e:
        st.error(f"HTTP Error: {e.response.status_code} - {e.response.reason}")
        st.error(f"Response Text: {e.response.text}")
        return False
    except Exception as e:
        st.error(f"Error downloading {url}: {str(e)}")
        return False

def parse_m3u8(m3u8_content, base_url):
    """Parse the .m3u8 file and extract .ts segment URLs."""
    segment_urls = []
    lines = m3u8_content.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        segment_url = line if line.startswith("http") else f"{base_url.rstrip('/')}/{line}"
        segment_urls.append(segment_url)
    return segment_urls

def download_m3u8_segments(m3u8_url, output_dir, headers, cookies):
    """Download the .m3u8 playlist and all .ts segments."""
    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Download the .m3u8 file
    m3u8_response = requests.get(m3u8_url, headers=headers, cookies=cookies)
    if not m3u8_response.ok:
        st.error(f"Failed to fetch .m3u8: {m3u8_response.status_code} - {m3u8_response.text}")
        return None
    m3u8_content = m3u8_response.text

    # Parse .ts segment URLs
    base_url = m3u8_url[:m3u8_url.rfind("/") + 1]
    segment_urls = parse_m3u8(m3u8_content, base_url)

    # Download each .ts segment
    segment_paths = []
    for i, segment_url in enumerate(segment_urls):
        segment_filename = f"segment_{i}.ts"
        segment_path = os.path.join(output_dir, segment_filename)
        if download_file(segment_url, segment_path, headers, cookies):
            segment_paths.append(segment_path)
        else:
            return None
    return segment_paths

def combine_ts_files(segment_paths, output_ts_path):
    """Combine all .ts files into a single .ts file."""
    with open(output_ts_path, "wb") as output_file:
        for segment_path in segment_paths:
            with open(segment_path, "rb") as segment_file:
                output_file.write(segment_file.read())
    st.write(f"Combined segments into: {output_ts_path}")

def convert_to_mp3(input_ts_path, output_mp3_path):
    """Convert the combined .ts file to MP3 using FFmpeg."""
    try:
        stream = ffmpeg.input(input_ts_path)
        stream = ffmpeg.output(stream, output_mp3_path, format="mp3", acodec="mp3", b="192k")
        ffmpeg.run(stream, overwrite_output=True)
        st.write(f"Converted to MP3: {output_mp3_path}")
        return True
    except ffmpeg.Error as e:
        st.error(f"Error during conversion: {e.stderr.decode()}")
        return False

def main():
    st.title("Audio Downloader")
    st.write("Enter the .m3u8 URL and JSESSIONID to download the audio as MP3.")

    # Input fields
    m3u8_url = st.text_area(
        ".m3u8 URL",
        "https://laharinagar.com/api/gurudev/app/files/audio/messages/1967/SEPTEMBER/1967.09.22%20NEW%20YORK%20(TESTIMONY)/index.m3u8",
        height=100
    )
    jsessionid = st.text_input("JSESSIONID", "87455767E32B4B31282D2FEB52405A71")

    if st.button("Download MP3"):
        with st.spinner("Processing..."):
            # Set cookies
            cookies = {"JSESSIONID": jsessionid}

            # Extract filename from URL
            url_parts = m3u8_url.split("/")
            file_base = url_parts[-2].replace("%20", "_")
            output_ts = os.path.join(OUTPUT_DIR, f"{file_base}.ts")
            output_mp3 = os.path.join(OUTPUT_DIR, f"{file_base}.mp3")

            st.write(f"Starting download from: {m3u8_url}")
            segment_paths = download_m3u8_segments(m3u8_url, OUTPUT_DIR, DEFAULT_HEADERS, cookies)

            if segment_paths:
                combine_ts_files(segment_paths, output_ts)
                if convert_to_mp3(output_ts, output_mp3):
                    # Provide download button
                    with open(output_mp3, "rb") as f:
                        st.download_button(
                            label="Download MP3",
                            data=f,
                            file_name=f"{file_base}.mp3",
                            mime="audio/mpeg"
                        )
                    # Clean up temporary files
                    for segment_path in segment_paths:
                        os.remove(segment_path)
                    os.remove(output_ts)
                    st.write("Cleaned up temporary files.")
                else:
                    st.error("Conversion to MP3 failed.")
            else:
                st.error("Failed to download audio segments.")

if __name__ == "__main__":
    main()