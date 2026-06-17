{ config, pkgs, modulesPath, lib, ... }:

let
  py = pkgs.python3;

  # NIX-01: NixOS buildPythonPackage expressions for google-adk 2.2.0,
  # langgraph 1.2.5, and weaviate-client 4.21.3.
  #
  # These expressions are a STANDALONE OVERLAY — import this file into your
  # agent flake's configuration.nix via the `imports` list when you need
  # the ADK stack available inside a NixOS LXC container.
  #
  # Open Question 1 (RESEARCH.md, RESOLVED 2026-06-16):
  # google-adk 2.2.0 has exactly ONE native extension in its transitive dep
  # chain: `cryptography`, reached via google-auth[requests] → google-genai.
  # grpcio does NOT appear in non-optional runtime deps (only in extras
  # `gcp`, `all`, `test`). Only `cryptography` needs a manylinux wheel.
  # All other runtime deps ship as py3-none-any pure-Python wheels.
  #
  # nix-prefetch: hashes below are placeholders.
  # To obtain the real hash for any fetchurl block, run:
  #   nix build --impure 2>&1 | grep "got:"
  # Copy the "got:" value and paste it as the hash for that fetchurl.
  # Repeat for each expression that prints a hash mismatch.

  # ---------------------------------------------------------------------------
  # cryptography 49.0.0 — native extension (Rust-based), manylinux x86_64
  # Reached via: google-adk → google-genai → google-auth[requests] → cryptography
  # Follows the jiter pattern from common-agent/configuration.nix.
  # Use cp311-abi3 (stable ABI) manylinux_2_17_x86_64 variant.
  # ---------------------------------------------------------------------------
  cryptography = py.pkgs.buildPythonPackage rec {
    pname = "cryptography";
    version = "49.0.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/20/2c/0622f20ff02b2ef32558733443805dc82fd4c275be01b2d19d14676f3a1b/cryptography-49.0.0-cp311-abi3-manylinux_2_28_x86_64.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-Kv6QUdp6571ZBdpalJKAx9K7dWguGI9lCp0PJ1a4NMY=";
    };
    propagatedBuildInputs = with py.pkgs; [ cffi ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # pyasn1 — required by google-auth transitive chain (pure-Python)
  # ---------------------------------------------------------------------------
  pyasn1 = py.pkgs.buildPythonPackage rec {
    pname = "pyasn1";
    version = "0.6.1";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/c8/f1/d6a797abb14f6283c0ddff96bbdd46937f64122b8c925cab503dd37f8214/pyasn1-0.6.1-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-DWMvRvK6CRQ9o6iv6eM/tvkvojIKt+iG4tD3Zyr4Rik=";
    };
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # pyasn1-modules — required by google-auth transitive chain (pure-Python)
  # ---------------------------------------------------------------------------
  pyasn1-modules = py.pkgs.buildPythonPackage rec {
    pname = "pyasn1_modules";
    version = "0.4.2";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/47/8d/d529b5d697919ba8c11ad626e835d4039be708a35b0d22de83a269a6682c/pyasn1_modules-0.4.2-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-KSU6kgfOMrZMOsZgDtx1No+YRzkG6P0QQ71rWx3iwUo=";
    };
    propagatedBuildInputs = [ pyasn1 ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # cachetools — required by google-auth (pure-Python)
  # ---------------------------------------------------------------------------
  cachetools = py.pkgs.buildPythonPackage rec {
    pname = "cachetools";
    version = "5.5.2";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/72/76/20fa66124dbe6be5cafeb312ece67de6b61dd91a0247d1ea13db4ebb33c2/cachetools-5.5.2-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-0moivMYuuVw76r2fHuXoINPScE/ilny+NQ4gyP/NPwo=";
    };
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # google-auth 2.40.3 — required by google-genai (pure-Python)
  # Transitive chain: google-adk → google-genai → google-auth
  # ---------------------------------------------------------------------------
  google-auth = py.pkgs.buildPythonPackage rec {
    pname = "google_auth";
    version = "2.40.3";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/17/63/b19553b658a1692443c62bd07e5868adaa0ad746a0751ba62c59568cd45b/google_auth-2.40.3-py2.py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-E3DUWT6GITVjVH+XqSdS/GWEVv5FFMgJVE8zD+1Fp8o=";
    };
    propagatedBuildInputs = with py.pkgs; [
      cachetools
      pyasn1-modules
      cryptography
      requests
    ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # google-genai — required by google-adk (pure-Python)
  # google-adk 2.2.0 requires google-genai>=2.4,<3; upgraded from 1.20.0.
  # ---------------------------------------------------------------------------
  google-genai = py.pkgs.buildPythonPackage rec {
    pname = "google_genai";
    version = "2.8.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/e2/de/747ad1aa49e902da9a4699081c282a1ed8ceed3b4d295fd99a6d286e09e4/google_genai-2.8.0-py3-none-any.whl";
      hash = "sha256-TaCiI6EA9LN/YJpouDXjMmqw+jEzFNwP2dNOdu4pOEQ=";
    };
    propagatedBuildInputs = with py.pkgs; [
      google-auth
      httpx
      pydantic
      requests
      typing-extensions
    ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # authlib — required by google-adk (pure-Python)
  # ---------------------------------------------------------------------------
  authlib = py.pkgs.buildPythonPackage rec {
    pname = "Authlib";
    version = "1.6.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/84/29/587c189bbab1ccc8c86a03a5d0e13873df916380ef1be461ebe6acebf48d/authlib-1.6.0-py2.py3-none-any.whl";
      hash = "sha256-kWhViUmPeehlXoqJR0Ma1iiIMdZD8RxVwhQ//Mc4BI0=";
    };
    propagatedBuildInputs = with py.pkgs; [ cryptography ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # opentelemetry-sdk — required by google-adk (pure-Python)
  # Provides opentelemetry.sdk.* instrumentation used by ADK tracing.
  # ---------------------------------------------------------------------------
  opentelemetry-sdk = py.pkgs.buildPythonPackage rec {
    pname = "opentelemetry_sdk";
    version = "1.32.1";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/dc/00/d3976cdcb98027aaf16f1e980e54935eb820872792f0eaedd4fd7abb5964/opentelemetry_sdk-1.32.1-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-u6N7cKCAOGEyR7xCvu5agbDdykIsfX8bCXsyvxx+Lxc=";
    };
    propagatedBuildInputs = with py.pkgs; [
      opentelemetry-api
      typing-extensions
    ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # tzlocal — required by google-adk (pure-Python)
  # ---------------------------------------------------------------------------
  tzlocal = py.pkgs.buildPythonPackage rec {
    pname = "tzlocal";
    version = "5.3.1";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/c2/14/e2a54fabd4f08cd7af1c07030603c3356b74da07f7cc056e600436edfa17/tzlocal-5.3.1-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-6xpmw+9YR633qDTxvggAWBtoO1YI50+G7LzvirkbuF0=";
    };
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # google-adk 2.2.0 — main ADK package (pure-Python wheel)
  # google_adk-2.2.0-py3-none-any.whl
  # Direct deps: google-genai, pydantic, httpx, python-dotenv, click, graphviz,
  #   jsonschema, opentelemetry-sdk, opentelemetry-api, starlette, uvicorn,
  #   websockets, authlib, pyyaml, python-multipart, requests, tenacity,
  #   tzlocal, watchdog, aiosqlite
  # ---------------------------------------------------------------------------
  google-adk = py.pkgs.buildPythonPackage rec {
    pname = "google_adk";
    version = "2.2.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/64/f5/44a3b20b17bac130497f2d1dde8b93c90cfc026983cd94f24488d540ea70/google_adk-2.2.0-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-6989kx3CucWzDZlTWPwq6Z1ZWUxIpKr3SWhpzNLF8kU=";
    };
    propagatedBuildInputs = with py.pkgs; [
      google-genai
      pydantic
      httpx
      python-dotenv
      click
      graphviz
      jsonschema
      opentelemetry-api
      opentelemetry-sdk
      starlette
      uvicorn
      websockets
      authlib
      pyyaml
      python-multipart
      requests
      tenacity
      tzlocal
      aiosqlite
      watchdog
      distro
      fastapi
      opentelemetry-semantic-conventions
    ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # langgraph-checkpoint — required by langgraph (pure-Python)
  # ---------------------------------------------------------------------------
  langgraph-checkpoint = py.pkgs.buildPythonPackage rec {
    pname = "langgraph_checkpoint";
    version = "2.0.26";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/38/48/d7cec540a3011b3207470bb07294a399e3b94b2e8a602e38cb007ce5bc10/langgraph_checkpoint-2.0.26-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-rUkHhY7TIKII4UrAN+S5JE7By1qlRXBRgWauiyV1LOw=";
    };
    propagatedBuildInputs = with py.pkgs; [ pydantic ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # langchain-core — required by langgraph (pure-Python)
  # ---------------------------------------------------------------------------
  langchain-core = py.pkgs.buildPythonPackage rec {
    pname = "langchain_core";
    version = "0.3.65";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/54/f0/31db18b7b8213266aed926ce89b5bdd84ccde7ee2edf4cab14e3dd2bfcf1/langchain_core-0.3.65-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-gOj69unzMfjvco8/55NUnx0/skT8+eG9zsq2pvRmk5Q=";
    };
    propagatedBuildInputs = with py.pkgs; [
      pydantic
      httpx
      typing-extensions
      tenacity
      pyyaml
    ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # langgraph 1.2.5 — graph-based agent framework (pure-Python wheel)
  # Direct deps: langchain-core, langgraph-checkpoint, pydantic
  # ---------------------------------------------------------------------------
  langgraph = py.pkgs.buildPythonPackage rec {
    pname = "langgraph";
    version = "1.2.5";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/a2/03/187281cf61845c5a9c397ae6cd9cd73bb54b39435e5575a7b83c853e5b76/langgraph-1.2.5-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-koa7Xe+C/IZZWcFDeP5HNRjcCX1YYiX2IvApY3oqS7k=";
    };
    propagatedBuildInputs = with py.pkgs; [
      pydantic
      langchain-core
      langgraph-checkpoint
    ];
    doCheck = false;
  };

  # grpcio — use nixpkgs build (1.76.0); manylinux wheels fail on NixOS due to
  # missing ld paths. nixpkgs grpcio is compiled natively against NixOS glibc.
  grpcio = py.pkgs.grpcio;

  # ---------------------------------------------------------------------------
  # weaviate-client 4.21.3 — Weaviate Python client (pure-Python wheel)
  # Direct deps: httpx, pydantic, grpcio (for gRPC transport)
  # Note: grpcio IS a non-optional dep for weaviate-client 4.x gRPC operations.
  # Unlike google-adk where grpcio is only in extras, weaviate-client uses
  # gRPC as its primary transport protocol.
  # ---------------------------------------------------------------------------
  weaviate-client = py.pkgs.buildPythonPackage rec {
    pname = "weaviate_client";
    version = "4.21.3";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/69/d6/ec1267a2a90fcbe1bb4b75cd6b946039ff8f282cac98d11d03ec08fc4732/weaviate_client-4.21.3-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-O+m+Jh4ByeZNhNDe7hqU6G+iXEG9yM3vUJkj/KMN7VM=";
    };
    propagatedBuildInputs = with py.pkgs; [
      httpx
      pydantic
      grpcio
      validators
      packaging
    ];
    doCheck = false;
  };

  # Python environment with ADK + langgraph + weaviate-client stack
  pythonEnv = py.withPackages (ps: with ps; [
    # google-adk 2.2.0 and its transitive deps
    google-adk
    google-genai
    google-auth
    cryptography
    pyasn1
    pyasn1-modules
    cachetools
    authlib
    opentelemetry-api
    opentelemetry-sdk
    tzlocal
    # langgraph 1.2.5 and its transitive deps
    langgraph
    langchain-core
    langgraph-checkpoint
    # weaviate-client 4.21.3 and its native dep
    weaviate-client
    grpcio
    # shared deps
    pydantic
    httpx
    anyio
    typing-extensions
    requests
    pyyaml
    aiosqlite
  ]);

in
{
  imports = [
    "${modulesPath}/virtualisation/proxmox-lxc.nix"
  ];

  proxmoxLXC = {
    privileged = false;
    manageNetwork = true;
    manageHostName = true;
  };

  networking.hostName = "adk-agent";
  networking.useDHCP = false;
  networking.enableIPv6 = false;

  # IP address, gateway, and DNS are injected by Proxmox at container creation
  # time via the net0=...,ip=<cidr>,gw=<gw> create parameter — do NOT hardcode.
  # See agents/teams-email-agent/configuration.nix for the correct pattern.

  services.resolved.enable = false;
  systemd.network.wait-online.enable = false;

  environment.systemPackages = [ pythonEnv ];

  # Activation: copy the NIX-01 import validation test script
  system.activationScripts.adkTestScript = ''
    mkdir -p /opt/suyam/nix
    cp ${./test-adk-imports.py} /opt/suyam/nix/test-adk-imports.py
    chmod +x /opt/suyam/nix/test-adk-imports.py
  '';

  system.stateVersion = "25.11";
}
