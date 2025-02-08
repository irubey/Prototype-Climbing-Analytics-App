# SendSage Core CSS Documentation

## Overview

This document explains the **core CSS files** used in the SendSage application. The CSS architecture is modular and built using **CSS Custom Properties** for design tokens such as colors, spacing, typography, shadows, and transitions. Each file has a distinct responsibility—from global resets and variables to component-specific styles—which ensures a scalable, responsive, and maintainable styling system.

---

## File Documentation

### 1. `static/css/_variables.css`

This file establishes all global **design tokens**. It defines variables for:

- **Color System:** Primary, secondary, accent colors as well as extended colors (e.g., coral, lavender) and gradients.
- **Typography:** Font families, sizes (including responsive and mobile-specific sizes), weights, and line-heights.
- **Spacing and Layout:** Base spacing units, container sizes, grid gaps, and responsive spacing utilities.
- **Components:** Border radius, shadows, and transitions.

All these variables ensure that any change (e.g., updating the primary color or adjusting spacing) automatically propagates throughout the application.

---

### 2. `static/css/_responsive.css`

This file provides **responsive utilities** using media queries based on defined breakpoints. Key functions include:

- **Container Adjustments:** The `.container` class adapts its maximum width per breakpoint.
- **Responsive Typography:** Adjusts base font sizes and heading scales using clamp functions.
- **Utility Classes and Grids:** Classes like `.hide-sm` and responsive grid column definitions (e.g., `.grid-cols-md-3`) improve the layout on different devices.

This approach helps maintain an adaptive UI without rewriting base styles.

---

### 3. `static/css/_base.css`

The base stylesheet sets the groundwork for styling:

- **Reset & Defaults:** Sets box sizing, margin, padding, and text smoothing to create a neutral starting point.
- **Typography Scale:** Defines basic typography for headings, paragraphs, lists, and other HTML elements.
- **Global Styles:** Basic element styling such as form controls, images, videos, and media elements are normalized.

This file forms the foundation upon which all component and layout styles build.

---

### 4. `static/css/_landingPage.css`

This stylesheet is tailored for the **landing page** experience:

- **Full-Screen Layout:** Overrides the global container styles to ensure the landing page occupies 100% of the viewport without scrolling.
- **Background Overlays:** Implements fixed background overlays with gradient effects and background images.
- **Form and Button Customizations:** Styles input fields, error messages, and various buttons to fit the landing page aesthetic.
- **Responsive Adjustments:** Ensures that elements such as input fields and button groups adapt smoothly on mobile devices.

By isolating these styles, the landing page can be easily updated without affecting other parts of the application.

---

### 5. `static/css/loadingScreen.css`

This file manages the application's **loading screen**:

- **Fixed Overlay:** Displays a fullscreen overlay with semi-transparent backgrounds to cover the entire UI during loading.
- **Animations:** Contains keyframe animations for fading, spinning, and background image transitions (e.g., cycling through different loading images).
- **Staged Transitions:** Implements multiple stages for loading with visual cues that indicate progress.

These styles ensure that users experience a smooth and engaging transition while the application asynchronously loads.

---

### 6. `static/css/pyramidInputs.css`

Dedicated to the **pyramid input interface**:

- **Table Container Styling:** Provides a scrollable, responsive container with sticky headers for performance tables.
- **Input Elements:** Customizes text inputs, radio groups, and numeric controls with focus, hover, and disabled states.
- **Column Layouts:** Defines styles for various columns (e.g., route-info, attempts, characteristics) used in the pyramid interface.
- **Additional Components:** Adds styling for descriptive text areas and action buttons (e.g., remove buttons) with consistent spacing and borders.

This file is critical for creating an intuitive user interface for performance data entry.

---

### 7. `static/css/_components.css`

This file contains the styles for all **reusable UI components**:

- **Form Elements & Inputs:** Styles radio groups, checkboxes, and other form controls with hover and active states.
- **Buttons and Action Elements:** Provides multiple button styles such as primary, secondary, add-route, delete, and notes buttons with transitions and hover effects.
- **Cards & Modals:** Defines card layouts, modal dialogs, alert banners, and info boxes to maintain consistency in information display.
- **Dashboard Items:** Includes quick stats, recent sends listings, and filter components designed to operate cohesively within varied screen sizes.

The modular nature of these components simplifies reuse across different parts of the application.

---

### 8. `static/css/_layout.css`

The primary file for **structural and grid layouts**:

- **Main Container:** Establishes the central container with max-width settings, margin, and padding.
- **Header and Footer:** Styles for navigation, branding, and footer link arrangements.
- **Grid Systems:** Defines multiple grid layouts including card grids, links rows, and metrics grids, ensuring proper spacing and alignment.
- **Responsive Layouts:** Contains media queries to adjust padding, container width, and layout structure based on device size.

This file is pivotal in providing the backbone of the application layout.

---

### 9. `static/css/visualizations.css`

This stylesheet covers the styles for data **visualization components**:

- **Performance Pyramid:** Styles the container hosting SVG graphics including overflow settings and fixed minimum dimensions.
- **SVG and Chart Elements:** Ensures that SVG elements scale appropriately and remain legible on various devices.
- **Tooltips and Legends:** Provides clear styling for interactive tooltips, legend items, and hover effects to communicate data insights.
- **Data Tables:** Includes styling for tables within visualizations to maintain readability and consistency.
- **Responsive Adjustments:** Adapts typography and spacing for mobile devices to ensure the visualization remains accessible.

The focus here is on delivering clear, interactive visuals and analytics without compromising responsiveness.

---

## Conclusion

The SendSage CSS architecture splits responsibilities among files to ensure a **scalable, performant, and maintainable** frontend codebase. By leveraging centralized variables, modular resets, responsive utilities, and component-specific styles, developers can more easily manage updates and maintain a consistent user experience across devices.

Each file targets a specific aspect of the UI, from establishing baseline styles and responsive layouts to building interactive components and animations. This documentation should serve as a valuable guide for both current and future developers working within the SendSage codebase.
