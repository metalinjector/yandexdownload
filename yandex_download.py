#!/usr/bin/env python3
"""Download a small, selected part of a public Yandex Disk folder.

Uses Yandex Disk's public-resource API and needs no OAuth token or third-party
packages.  The API returns a short-lived direct URL; it is deliberately not
stored in a manifest.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

API = "https://cloud-api.yandex.net/v1/disk/public/resources"
DEFAULT_LINK = "https://disk.yandex.ru/d/7kjMhZNdWtEQmA"


def api_url(public_link: str, *, path: str | None = None, download=False) -> str:
    endpoint = API + ("/download" if download else "")
    query = {"public_key": public_link}
    if path:
        query["path"] = path
    return endpoint + "?" + urlencode(query, quote_via=quote)


def request_json(url: str, retries: int = 3) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"Accept": "application/json", "User-Agent": "yandexdownload/1.0"})
            with urlopen(req, timeout=60) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise RuntimeError("Yandex API returned non-object JSON")
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Yandex API request failed: {last}") from last


def list_folder(public_link: str, path: str = "/") -> dict[str, Any]:
    return request_json(api_url(public_link, path=path))


def items(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    embedded = metadata.get("_embedded", {})
    result = embedded.get("items", []) if isinstance(embedded, dict) else []
    return [item for item in result if isinstance(item, dict)]


def walk_files(public_link: str, folder: str) -> Iterator[dict[str, Any]]:
    for item in items(list_folder(public_link, folder)):
        item_path = str(item.get("path", "/"))
        if item.get("type") == "file":
            yield item
        elif item.get("type") == "dir":
            yield from walk_files(public_link, item_path)


def safe_relative_path(item_path: str, base: str) -> Path:
    """Turn an API path into a local path and reject traversal/absolute paths."""
    base_parts = [p for p in PurePosixPath(base).parts if p not in ("/", "")]
    path_parts = [p for p in PurePosixPath(unquote(item_path)).parts if p not in ("/", "")]
    if path_parts[: len(base_parts)] == base_parts:
        path_parts = path_parts[len(base_parts) :]
    if not path_parts or any(p in (".", "..") for p in path_parts):
        raise ValueError(f"unsafe resource path: {item_path!r}")
    return Path(*path_parts)


def download_file(public_link: str, item: dict[str, Any], base: str, destination: Path) -> Path:
    relative = safe_relative_path(str(item["path"]), base)
    output = destination / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and item.get("size") == output.stat().st_size:
        return output
    info = request_json(api_url(public_link, path=str(item["path"]), download=True))
    direct = info.get("href")
    if not isinstance(direct, str) or not direct.startswith("https://"):
        raise RuntimeError(f"Yandex did not provide a download URL for {item.get('path')}")
    temporary = output.with_name(output.name + ".part")
    req = Request(direct, headers={"User-Agent": "yandexdownload/1.0"})
    try:
        with urlopen(req, timeout=120) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download a selected part of a public Yandex Disk folder")
    parser.add_argument("link", nargs="?", default=DEFAULT_LINK, help="public Yandex Disk URL")
    parser.add_argument("--folder", default="/", help="folder inside the public resource, e.g. 'Singles & EPs'")
    parser.add_argument("--output", type=Path, default=Path("downloads"))
    parser.add_argument("--max-files", type=int, default=1, help="maximum files (default: 1, keeps the download minimal)")
    parser.add_argument("--max-bytes", type=int, default=100 * 1024 * 1024)
    parser.add_argument("--list", action="store_true", help="only list files; do not download")
    args = parser.parse_args(argv)
    if args.max_files < 1 or args.max_bytes < 1:
        parser.error("--max-files and --max-bytes must be positive")
    folder = args.folder if args.folder.startswith("/") else "/" + args.folder
    try:
        selected = []
        total = 0
        for item in walk_files(args.link, folder):
            size = int(item.get("size") or 0)
            if len(selected) >= args.max_files or total + size > args.max_bytes:
                break
            selected.append(item)
            total += size
        if not selected:
            raise RuntimeError("No files found in the selected folder (or limits are too small)")
        for item in selected:
            print(f"{item.get('path')}\t{item.get('size', 0)} bytes")
        if args.list:
            return 0
        for item in selected:
            print(f"Downloading {item['path']} ...")
            print(f"Saved: {download_file(args.link, item, folder, args.output)}")
        print(f"Done: {len(selected)} file(s), {total} bytes")
        return 0
    except (RuntimeError, ValueError, OSError, HTTPError, URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
