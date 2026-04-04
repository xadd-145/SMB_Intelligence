# Microsoft SMB Intelligence Engine

A production-style analytics engineering and decision intelligence system designed to identify **which SMB customers Microsoft should act on today — and exactly what action to take — to maximize revenue retention and growth.**

---

## Executive Summary

Most organizations rely on static dashboards to monitor customer health. This project builds a **decision system**, not a report.

It ingests raw SMB telemetry, transforms it into behavioral signals, predicts churn risk, and translates those predictions into **clear, prioritized business actions**.

> **Outcome:**  
> Identify high-value SMB accounts at risk and generate targeted retention or expansion strategies — enabling faster, data-driven sales decisions.

---

## Business Problem

Microsoft’s SMB organization must continuously answer:

- Which customers are at risk of churn?
- Which accounts are ready for expansion?
- Where should sales teams focus *today*?

Traditional reporting is reactive.  
This system enables **proactive intervention** using data-driven signals.

---

## Core Question

> **Which SMB customers should Microsoft act on today — and what specific action should each account receive — to maximize revenue retention and growth?**

---

## Architecture Overview

A medallion-style pipeline built in Microsoft Fabric:

```mermaid
flowchart LR
    A[Raw Telemetry CSV] --> B[Bronze Layer]
    B --> C[Silver Layer]
    C --> D[Gold Layer]
    D --> E[Churn Model]
    E --> F[Decision Engine]
    F --> G[Power BI Dashboard]
