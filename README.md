# 📖 Smart EPUB Reader & Annotation System

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-lightgrey.svg)
![SQLite](https://img.shields.io/badge/SQLite-Database-green.svg)
![Vanilla JS](https://img.shields.io/badge/Vanilla_JS-DOM_Manipulation-yellow.svg)
![epub.js](https://img.shields.io/badge/epub.js-Rendering_Engine-blueviolet.svg)

A web-based EPUB reader focusing on an advanced, dynamic annotation and highlighting system. Built with Python (Flask) and SQLite, this application goes beyond simple reading by turning your ebooks into interconnected study materials.

**🌐 Live Demo:** [Try the application here!](https://namakamu.pythonanywhere.com)  

**Demo Credentials:**
* **Username:** `demo`
* **Password:** `demo123`

> **Note:** This application is designed as a personal library. Logging in with the demo account will grant you full access to view, upload, and interact with the globally shared EPUB collection and its smart annotations.

## ✨ Core Feature: Global Smart Highlighting

This project implements a complex text-parsing and DOM manipulation engine:
* **Contextual Highlighting & Notes:** Users can select any text within the EPUB and attach a custom note.
* **Global Instance Tracking:** Once a note is saved, the system dynamically scans the rendered EPUB content and automatically applies an `underline` style to **every identical word or phrase** throughout the book.
* **Interactive Pop-ups:** Clicking on any of the globally underlined words will instantly trigger a pop-up displaying the original note attached to that specific term, creating a seamless cross-referencing experience.

## 🏗️ Technical Architecture & DOM Manipulation

Unlike heavy framework-based readers, this application is engineered for maximum performance using a hybrid DOM manipulation approach:

* **Iframe Rendering Engine (`epub.js`):** Acts as the core rendering engine isolated strictly within the iframe. It handles complex dynamic pagination (parsing raw `.xhtml` on the fly) and precise DOM injection for the global smart highlighting system using CFI coordinates.
* **Vanilla JavaScript Interface:** The entire outer user interface (TOC generation, pop-ups, and chapter titles) is built with pure Vanilla JS. By manipulating the DOM directly (`document.createElement`, `appendChild`), the app remains incredibly lightweight and fast.
* **Passive DOM Surveillance (`MutationObserver`):** Instead of forced polling, the app implements the `MutationObserver` API to passively watch the `<html>` tags. This acts as a high-tier "CCTV," allowing the system to react efficiently to external DOM mutations (such as Google Chrome's auto-translate injections) without degrading performance.

## 🛠️ Additional Features

* **Personal Ebook Library:** Upload, parse, and organize your `.epub` files effortlessly.
* **Lightweight Architecture:** Powered by SQLite and Flask for fast querying and easy deployment without heavy database server requirements.
* **Responsive Web Reader:** A clean, distraction-free reading interface that adapts seamlessly to your browser window.
