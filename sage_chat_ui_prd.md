# SendSage UI Overhaul PRD

## 1. Product Overview

SendSage is an AI-powered climbing coach and analytics platform. The upcoming UI overhaul aims to consolidate the SageChat and onboarding (settings) components under a single layout with three main tabs—Chat, Settings, and Visualizations—delivering an intuitive and engaging user experience. Inspired by the creative interactivity of the cursed-cursor article, this iteration will introduce subtle micro-interactions and fluid animations to delight users without compromising clarity or performance.

## 2. Business Objectives

- **Enhance User Engagement**: Provide a dynamic "home base" where both casual and premium users quickly access chat features and settings.
- **Improve Navigation and Onboarding**: Ensure that new or returning users can easily switch between real-time conversations (SageChat) and profile updates (onboarding and subscription management).
- **Elevate User Experience**: Leverage novel visual and interactive elements (inspired by cursed-cursor) to add personality without sacrificing performance or accessibility.

## 3. Target User Personas

- **Casual Climbers** (Free tier): Users who primarily use the free visualization suite and require a straightforward, engaging interface.
- **Premium Climbers** (Paid tier): Users who rely on SageChat for personalized coaching with more advanced features and may also need access to subscription management within the settings tab.

## 4. Feature and Functional Requirements

### 4.1 Main Display Area

#### Tab Navigation

The base presents a tab navigation bar with three tabs:

- **Chat Tab**: Displays the interactive messaging interface (rendered via the existing chat_interface() macro)
- **Settings Tab**: Contains the onboarding form, profile update options, and a link/button for Stripe subscription management (rendered via the existing settings() macro)
- **Visualizations Tab**: Immediately redirects the user to /logbook-connection

#### Conditional Rendering

Default active view depends on the user's onboarding status:

- Fully onboarded users see the Chat tab by default
- Incomplete profiles default to the Settings tab

### 4.2 User Interactions

#### Tab Switching

- Switching between Chat and Settings handled via client-side JavaScript with smooth transitions
- Current tab selection persists on page refresh (via local storage)

#### Animations and Micro-Interactions

- Subtle animated effects inspired by the cursed-cursor example
- Light cursor animations and micro-interactions on tab hover
- Performance and accessibility remain uncompromised

### 4.3 Error Handling and Loading States

#### Chat and Form Feedback

- Visual indicators for asynchronous operations
- Inline error messages for network timeouts or backend errors
- Non-blocking interactions maintained

#### Subscription Status Alerts

- Non-intrusive banner or modal alerts for subscription changes
- Direct links to subscription management

### 4.4 Performance and Accessibility

#### Performance Requirements

- Rapid UI loading
- Minimal latency for real-time chat
- Consideration for lazy-loading and caching

#### Accessibility Standards

- WCAG 2.1 AA compliance
- Keyboard navigability
- Proper ARIA roles
- Clear focus indicators
- Sufficient contrast ratios

## 5. Technical Requirements

### Frontend

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>SendSage - Chat and Settings</title>
    <link
      rel="stylesheet"
      href="{{ url_for('static', filename='css/chat.css') }}"
    />
  </head>
  <body>
    <div class="tab-nav">
      <button id="tab_chat" class="tab-button active">Chat</button>
      <button id="tab_settings" class="tab-button">Settings</button>
      <button
        id="tab_visualizations"
        class="tab-button"
        onclick="window.location.href='/logbook-connection'"
      >
        Visualizations
      </button>
    </div>

    <div id="main_content">
      <div id="chat_view">{{ chat_interface() }}</div>
      <div id="settings_view" style="display: none;">
        {{ settings() }}
        <a href="{{ url_for('main.payment') }}" class="btn btn-secondary"
          >Change Subscription</a
        >
      </div>
    </div>

    <script src="{{ url_for('static', filename='js/chat_tabs.js') }}"></script>
  </body>
</html>
```

### Client-Side Logic

```javascript
document.addEventListener("DOMContentLoaded", function () {
  const chatTab = document.getElementById("tab_chat")
  const settingsTab = document.getElementById("tab_settings")
  const chatView = document.getElementById("chat_view")
  const settingsView = document.getElementById("settings_view")

  // Load the active tab from local storage
  let activeTab = localStorage.getItem("activeTab") || "chat"
  if (activeTab === "settings") {
    settingsTab.classList.add("active")
    chatTab.classList.remove("active")
    settingsView.style.display = "block"
    chatView.style.display = "none"
  }

  chatTab.addEventListener("click", function () {
    chatTab.classList.add("active")
    settingsTab.classList.remove("active")
    chatView.style.display = "block"
    settingsView.style.display = "none"
    localStorage.setItem("activeTab", "chat")
  })

  settingsTab.addEventListener("click", function () {
    settingsTab.classList.add("active")
    chatTab.classList.remove("active")
    settingsView.style.display = "block"
    chatView.style.display = "none"
    localStorage.setItem("activeTab", "settings")
  })
})
```

### Backend Route

```python
@main_bp.route("/sage-chat")
@login_required
@temp_user_check
@payment_required
def sage_chat():
    user_id = current_user.id
    try:
        summary_service = ClimberSummaryService(user_id=user_id)
        initial_summary = ClimberSummary.query.get(user_id)
        if not initial_summary:
            initial_summary = summary_service.update_summary()
        else:
            initial_summary = summary_service.update_summary()

        data_complete = check_data_completeness(initial_summary)

        return render_template(
            'chat/main.html',
            user_id=user_id,
            initial_summary=initial_summary,
            initial_data_complete=data_complete,
            routes_grade_list=[],  # Populate with data from GradeProcessor if needed
            boulders_grade_list=[]
        )
    except Exception as e:
        current_app.logger.error(f"Error in sage_chat: {str(e)}")
        return "An error occurred", 500
```

## 5.2 Template File Structure

```
app/
├── templates/
│ ├── chat/
│ │ ├── main.html  # Main layout for the three-tab interface that includes tab navigation and two main content areas
│ │ └── partials/
│ │  ├── chatInterface.html # Contains the macro for rendering the chat interface.
│ │  ├── settings.html # Contains the macro for rendering the settings view (onboarding form + subscription link)
│ │  └── advanced_settings.html # Contains the macro for rendering the advanced settings view which includes all the editable fields in the onboarding form
```

## 6. Implementation Plan

### Step 1: Template Structure Setup

- Create unified main template for three tabs
- Implement navigation bar and content areas
- Integrate existing macros
- Add subscription management button

### Step 2: Client-Side Implementation

- Develop tab switching logic
- Implement state persistence
- Add smooth transitions and animations
- Ensure performance optimization

### Step 3: Backend Integration

- Update route handlers
- Implement context variable passing
- Verify data completeness checks
- Error handling implementation

### Step 4: Testing and Deployment

- Unit/Integration testing
- User acceptance testing
- Performance validation
- Accessibility compliance
- Staged rollout

## 7. Acceptance Criteria

- Three-tab navigation with clear labeling
- Functional Visualizations redirect
- Smooth tab transitions with state persistence
- Complete subscription management integration
- Performance-optimized animations
- Full accessibility compliance

## 8. Risk Mitigation

- **Performance**: Optimize animations using requestAnimationFrame
- **Navigation**: Thorough UX testing for intuitive layout
- **Compatibility**: Maintain existing endpoints with fallback mechanisms
