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
      url = "https://files.pythonhosted.org/packages/cp311/c/cryptography/cryptography-49.0.0-cp311-abi3-manylinux_2_28_x86_64.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_cryptography_49_manylinux=";
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
      url = "https://files.pythonhosted.org/packages/py3/p/pyasn1/pyasn1-0.6.1-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_pyasn1=";
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
      url = "https://files.pythonhosted.org/packages/py3/p/pyasn1_modules/pyasn1_modules-0.4.2-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_pyasn1_modules=";
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
      url = "https://files.pythonhosted.org/packages/py3/c/cachetools/cachetools-5.5.2-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_cachetools=";
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
      url = "https://files.pythonhosted.org/packages/py3/g/google_auth/google_auth-2.40.3-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_google_auth=";
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
  # Pinned to the version shipped with google-adk 2.2.0.
  # ---------------------------------------------------------------------------
  google-genai = py.pkgs.buildPythonPackage rec {
    pname = "google_genai";
    version = "1.20.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/g/google_genai/google_genai-1.20.0-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_google_genai=";
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
      url = "https://files.pythonhosted.org/packages/py3/A/Authlib/Authlib-1.6.0-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_authlib=";
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
      url = "https://files.pythonhosted.org/packages/py3/o/opentelemetry_sdk/opentelemetry_sdk-1.32.1-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_opentelemetry_sdk=";
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
      url = "https://files.pythonhosted.org/packages/py3/t/tzlocal/tzlocal-5.3.1-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_tzlocal=";
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
      url = "https://files.pythonhosted.org/packages/py3/g/google_adk/google_adk-2.2.0-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_google_adk=";
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
      url = "https://files.pythonhosted.org/packages/py3/l/langgraph_checkpoint/langgraph_checkpoint-2.0.26-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_langgraph_checkpoint=";
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
      url = "https://files.pythonhosted.org/packages/py3/l/langchain_core/langchain_core-0.3.65-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_langchain_core=";
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
      url = "https://files.pythonhosted.org/packages/py3/l/langgraph/langgraph-1.2.5-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_langgraph=";
    };
    propagatedBuildInputs = with py.pkgs; [
      pydantic
      langchain-core
      langgraph-checkpoint
    ];
    doCheck = false;
  };

  # ---------------------------------------------------------------------------
  # grpcio 1.73.0 — native extension (C-based), manylinux x86_64
  # Required by weaviate-client for gRPC transport.
  # Follows the jiter pattern from common-agent/configuration.nix.
  # ---------------------------------------------------------------------------
  grpcio = py.pkgs.buildPythonPackage rec {
    pname = "grpcio";
    version = "1.73.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/cp312/g/grpcio/grpcio-1.73.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_grpcio_manylinux=";
    };
    doCheck = false;
  };

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
      url = "https://files.pythonhosted.org/packages/py3/w/weaviate_client/weaviate_client-4.21.3-py3-none-any.whl";
      # nix-prefetch: run nix build --impure 2>&1 | grep "got:"
      hash = "sha256-PLACEHOLDER_weaviate_client=";
    };
    propagatedBuildInputs = with py.pkgs; [
      httpx
      pydantic
      grpcio
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
