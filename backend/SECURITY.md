# Security and Bounty-Hunting Policy

## Overview

Thank you for your interest in improving the security of our project. We appreciate your efforts to make our software better and more secure.

This document outlines the policies regarding security vulnerability reporting and bounty-hunting activities within this project.

We are particularly interested in whether you were able to gain unauthorized access (e.g., logging in via hacking) to areas and data that should be restricted. Additionally, we highly value contributions that include a patch. Please consider submitting a patch to our GitHub repository with your proposed implementation via a pull request or any other method you prefer for this open-source project.

## Bounty Program

We offer bounties for finding and responsibly disclosing vulnerabilities in our project. The size of the bounty is determined by the severity of the vulnerability as assessed by the DTU Security Operations Center (DTU-SOC) using the CWS (Common Weakness Scoring) system.

### Definition of a Vulnerability

A vulnerability is defined by the DTU Security Operations Center (DTU-SOC) when it is exposed in our systems. The severity and impact of the vulnerability are evaluated using the Common Weakness Scoring (CWS) system.

### Bounty Rewards

The rewards for reporting vulnerabilities are given in the form of cases of soda (e.g., Faxi Kondi, Cola, Pepsi, Fanta). The number of cases awarded is based on the CWS severity score. Rewards are only given if approved, and you must be an employee or student at DTU and a member of hackerlab.dtu.dk to be eligible for a reward. Additionally, rewards are given if you find a vulnerability and preferrably, but not needed, push a patch to this repository that fixes the problem.

- **CWS Score: 10** — 1 case (24x0.33cl) of soda (e.g., Faxi Kondi, Cola, Pepsi, Fanta)
- **CWS Score: 8** — 1 case (24x0.33cl) of soda (e.g., Faxi Kondi, Cola, Pepsi, Fanta)
- **CWS Score: 6** — 1 case (24x0.33cl) of soda (e.g., Faxi Kondi, Cola, Pepsi, Fanta)
- **CWS Score: 4** — 1 case (24x0.33cl) of soda (e.g., Faxi Kondi, Cola, Pepsi, Fanta)
- **CWS Score: 2** — 1 case (24x0.33cl) of soda (e.g., Faxi Kondi, Cola, Pepsi, Fanta)

### Who Can Participate

- **DTU Students and Employees:** 
  - If you are a student or employee at the Technical University of Denmark (DTU) with a valid DTU email address (i.e., *@*.dtu.dk) and a member of hackerlab.dtu.dk, you are automatically authorized to participate in bounty hunting without needing prior permission.
  - **Forgivable Actions:** As long as you are a DTU student or employee, all actions conducted in the course of responsible bounty hunting are forgivable. We value your contributions and will work with you to address any issues that may arise. However, please note that just because actions are forgivable, it does not mean you should be disrespectful or inconsiderate in your approach.

- **External Participants:** 
  - If you are not a DTU student or employee, you **must** request permission before engaging in any bounty-hunting activities.
  - To request permission, please contact us at itsecurity@dtu.dk with your name, the scope of your planned testing, and a brief outline of your methodology.
  - Only after receiving explicit permission may you begin bounty-hunting activities.
  - If you do not obtain permission, any form of hacking will be considered illegal activity and will be subject to legal action in accordance with the law.

## Bounty-Hunting Guidelines

To ensure the safety and continuity of our services, all participants must adhere to the following guidelines:

- **Minimizing Disruption:** 
  - Participants should minimize any potential disruption to our services.
  - DDoS (Distributed Denial-of-Service) attacks should be avoided as much as possible and, if necessary, should only be conducted outside of standard working hours (Monday to Friday, 9 AM to 5 PM CET).

- **Scope of Testing:**
  - The scope of testing is limited to the following domains and IP addresses:
    - **Domains:** `api.security.ait.dtu.dk`
    - **IP Addresses:** `192.38.87.231`
  - Ensure your testing focuses only on these in-scope domains and IP addresses.
  - Out-of-scope testing will not be eligible for a bounty and may be considered a violation of this policy, except in cases where the participant is a DTU student or employee.

- **High-Interest Vulnerabilities:**
  - We are particularly interested in vulnerabilities that allow unauthorized access to data, applications, or systems. If you discover a way for an attacker to gain access to data or applications they should not have access to, this will be of high interest and likely to qualify for a higher bounty.

- **Reporting Vulnerabilities:**
  - All vulnerabilities must be reported via itsecurity@dtu.dk.
  - Include a detailed description of the vulnerability, steps to reproduce, potential impact, and any proposed mitigations.
  - The reported vulnerabilities will be evaluated by DTU-SOC, and the severity will be scored using the CWS system.

- **No Unauthorized Data Access:**
  - Do not attempt to access, modify, or delete any data that you do not own, unless this is part of the testing scope. DTU students and employees are encouraged to report any accidental access.

## Bounty Exclusions

The following types of findings generally do not qualify for a bounty:

- Out-of-scope domains or IPs, unless discovered by a DTU student or employee as part of responsible testing.
- Issues with no security impact (e.g., best practices, general feedback).
- Vulnerabilities resulting from outdated browsers or plugins.

## Contact Information

For any questions or to request permission to start bounty hunting, please contact us at:

- Email: itsecurity@dtu.dk

We look forward to working with you to keep our project safe and secure!
