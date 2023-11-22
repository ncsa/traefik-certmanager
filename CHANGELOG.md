# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## 1.1.0 - 2023-11-21

### Changed
- now monitors `traefik.io` as well as `traefik.containo.us`

### Added
- catch signals to exit quicker
- will add secretName to ingressRoute if missing (PATCH_SECRETNAME=true)

## 1.0.0 - 2022-10-09

This is the initial release. This will work with Traefik IngressRoutes and create Certificates from them.
