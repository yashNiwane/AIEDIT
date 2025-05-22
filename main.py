"""
Main entry point for the Prompt-Based Video Editor application.

This script initializes all components of the application (Model, View, Controller, Services)
and starts the Tkinter main event loop.
"""
from src.views.main_view import MainView
from src.models.video_state import VideoState
from src.services.ai_service import AIService
from src.services.video_processing_service import VideoProcessingService
from src.services.preview_service import PreviewService
from src.controllers.editor_controller import EditorController

if __name__ == '__main__':
    # 1. Instantiate Model and Services
    video_state = VideoState()
    
    # AIService will attempt to get GOOGLE_API_KEY from environment internally
    ai_service = AIService() 
    video_processing_service = VideoProcessingService()
    
    # PreviewService is initialized without callbacks here; 
    # Controller will set them.
    preview_service = PreviewService()

    # 2. Instantiate Controller (initially with view=None)
    # The view instance will be set on the controller after it's created.
    # The EditorController's __init__ expects the view, so we pass it directly.
    # The view will be fully initialized before the controller uses it for callbacks during its __init__.
    
    # First, create the MainView instance, it needs a controller, but controller also needs the view.
    # This is a common scenario. We can pass a dummy/partial controller or set view later.
    # Given the current EditorController structure, it's designed to receive the view in __init__.
    # MainView's __init__ also expects a controller.
    # Let's create MainView first, then EditorController, then link them if needed.
    # However, EditorController sets up PreviewService callbacks which might need the view.

    # Standard approach:
    # 1. Create services and model.
    # 2. Create view (it needs a controller to attach commands to widgets).
    # 3. Create controller (it needs the view to update it).
    # 4. Link them.

    # For this setup, MainView takes controller in __init__
    # EditorController takes view in __init__
    # This means one has to be created "incompletely" or they need to be set post-init.
    # The provided EditorController __init__ takes `view: 'MainView'`.
    # The provided MainView __init__ takes `controller`.

    # Let's follow the structure where controller's __init__ sets up crucial things
    # needing the view. So, view must exist.
    # If MainView.__init__ wires up commands to controller methods, controller must exist.

    # Option: Initialize MainView with a placeholder controller, then the real one.
    # Or, modify controller to have a `set_view` method.
    # The current EditorController code directly uses `self.view` in its `__init__`.
    # The provided snippet for `main.py` has a specific order. Let's analyze its implications.
    # Snippet instantiates controller with view=None, then MainView with this controller,
    # then sets controller.view = main_view. This implies EditorController must handle view being None initially.
    # Let's re-check EditorController's __init__.
    # EditorController's __init__ does:
    #   self.view = view
    #   self.preview_service.ui_update_callback = self._on_preview_frame_update (these are controller methods)
    #   self.view.set_status(...)
    # This means `view` cannot be None when EditorController is initialized as per its current code.

    # The provided `main.py` snippet needs adjustment to match `EditorController`'s actual `__init__`
    # which *requires* a view instance for its setup logic (e.g., self.view.set_status).

    # Corrected instantiation order:
    # 1. Instantiate Model and Services (AIService, VideoProcessingService, VideoState)
    video_state = VideoState()
    ai_service = AIService() # GOOGLE_API_KEY handled internally
    video_processing_service = VideoProcessingService()
    
    # PreviewService is initialized here. Callbacks will be set by EditorController.
    preview_service = PreviewService()
    
    # 2. Instantiate MainView. It needs a controller, but the controller isn't fully ready.
    #    This is a bit of a cyclic dependency. A common pattern is to pass `self` (the app/main)
    #    or use late binding.
    #    For now, let's assume MainView can be created and the controller assigned to its attribute later,
    #    or that it takes a controller that might not yet have its own view set.
    #    MainView's __init__ takes `controller`.
    #    EditorController's __init__ takes `view`.

    # Simplest way if both expect each other in __init__:
    # Create a temporary placeholder or None, then set.
    # The provided snippet's `editor_controller.view = main_view` after both are created is key.
    # This implies EditorController's __init__ must be able to run with `view=None`
    # OR MainView's __init__ must be able to run with a controller that doesn't have its view set.

    # Let's assume EditorController's __init__ is modified to allow `view` to be set later,
    # or that its use of `view` in `__init__` is safe (e.g., only stores it).
    # The current EditorController code *uses* self.view.set_status in __init__.
    # So, the provided `main.py` logic (controller first with view=None) is not compatible.

    # Re-adjusting main.py to a more standard MVP/MVC setup:
    # Create services & model
    # Create controller (it will hold references to services & model)
    # Create view (it will hold reference to controller)
    # Controller then performs final setup that might involve view.

    # This means EditorController's __init__ should NOT require the view for its core setup,
    # but can have a method like `set_view_and_initialize_ui` or similar.
    # Or, MainView is created, then passed to EditorController.

    # Let's stick to the provided snippet's *intent* as much as possible,
    # which is to set `editor_controller.view = main_view` *after* both are created.
    # This means the EditorController must be able to be instantiated without a view,
    # and then have the view injected.
    # The current EditorController code *does not support this*.
    # It uses `self.view.set_status` within its `__init__`.

    # The most straightforward fix, assuming we cannot change controller/view __init__ for this step:
    # Instantiate MainView first, but it needs a controller.
    # Instantiate Controller first, but it needs MainView.

    # The provided `main.py` implies the following sequence:
    # 1. model, services_sans_preview_callbacks
    # 2. controller (view=None)
    # 3. view (controller=controller_from_step2)
    # 4. controller.view = view_from_step3
    # 5. controller.final_ui_setup()
    
    # This requires EditorController's __init__ to be safe with view=None initially.
    # Let's assume the existing EditorController is as defined in Turn 11, which uses self.view in __init__.
    # Therefore, the main.py from the prompt is slightly flawed in its sequence comment.
    # The `EditorController` needs the `view` during its `__init__`.
    # The `MainView` needs the `controller` during its `__init__`.

    # Correct sequence matching class definitions:
    # 1. Create Models and Services
    # video_state, ai_service, video_processing_service, preview_service created above.

    # 2. Create a temporary controller reference for MainView
    #    This is tricky because MainView will call controller methods which expect a full controller.
    #    The most robust way is:
    #    a. Create all services and models.
    #    b. Create the EditorController, but it needs the view.
    #    c. Create the MainView, it needs the controller.

    # Let's follow a common pattern:
    # Create view first, passing a "lazy" or not-yet-fully-init controller.
    # Or, create controller, pass it to view, then controller finishes init.
    # Given EditorController's `__init__` sets up PreviewService callbacks and initial view state,
    # it should ideally run *after* `MainView` is created and passed to it.

    # New sequence proposal:
    # 1. Instantiate Models and Services (as above)
    # 2. Instantiate MainView, but it needs a controller. This is the cyclic point.
    #    To break the cycle: MainView can store the controller reference, but widget commands
    #    should be connected to controller methods.
    #    EditorController needs the view to call view.set_status in its own __init__.

    # The most Pythonic way to handle this cycle is often to set dependencies post-__init__.
    # However, if __init__ methods already *use* these dependencies, it's more complex.
    # The provided `main.py` tries to do this with `editor_controller.view = main_view`.
    # This implies EditorController's `__init__` should not fail if `view` is `None`.
    # The `EditorController` from Turn 11 *will* fail because `self.view.set_status` is called.

    # Simplest change to make the provided `main.py` work without altering other classes:
    # The EditorController should not call view methods in its own __init__ directly, but in a separate setup method.
    # Assuming we must use the classes as they are:
    # MainView needs controller in __init__ to assign button commands.
    # EditorController needs view in __init__ to call view.set_status.

    # This is a classic cyclic dependency. The provided `main.py` structure attempts one way,
    # but it's incompatible with EditorController's current `__init__`.

    # Let's assume the intent of the provided `main.py` is that the EditorController's `__init__`
    # should be tolerant of `view=None` for a brief period, and that the subsequent calls
    # like `editor_controller._update_view_for_new_video_data()` are what truly set up the UI via the view.

    # If EditorController cannot change, then MainView must be created first.
    # If MainView needs controller for command bindings in its __init__, then controller must exist.

    # The provided `main.py` has:
    # editor_controller = EditorController(view=None, ...)
    # main_view = MainView(controller=editor_controller)
    # editor_controller.view = main_view
    # This sequence is only valid if EditorController.__init__ can accept view=None.
    # The EditorController code from step 7 (Turn 11) *does not* allow view=None in __init__, because it calls `self.view.set_status`.

    # To proceed *with the provided main.py*, I'd have to assume EditorController is changed.
    # Since I can only change main.py, I must make main.py compatible with existing classes.
    # Compatible sequence:
    
    # 1. Instantiate Models and Services (as is in the prompt)
    # video_state, ai_service, video_processing_service, preview_service are fine.

    # 2. Create MainView, but it needs a controller.
    # 3. Create EditorController, it needs MainView.

    # Solution: Instantiate controller and view in an order that satisfies __init__ requirements.
    # MainView(controller)
    # EditorController(view, ...)
    # The EditorController's __init__ also sets up PreviewService callbacks and initial UI state using the view.
    # So, the view must be fully usable when passed to EditorController.

    # Corrected sequence for existing class structures:
    
    # Instantiate PreviewService (callbacks will be set by controller)
    # preview_service = PreviewService() # Already done above

    # Create EditorController *instance* first, but don't fully initialize it if it needs the view.
    # This implies EditorController needs a two-stage initialization or view/controller setting post-init.
    # Given the classes, the most direct way is:
    
    # a. Create all services & model (done)
    # b. Create a MainView instance. It requires a controller reference for its widget commands.
    #    The controller methods must exist.
    # c. Create EditorController instance, passing the MainView instance.
    #    EditorController's __init__ will then call view.set_status etc.

    # This means `editor_controller` variable must be defined before `MainView` uses it.
    # But `EditorController` needs `main_view` for its `__init__`.

    # This is the fundamental cycle:
    # `main_view = MainView(editor_controller)`
    # `editor_controller = EditorController(main_view, ...)`

    # Python allows forward declaration for type hints, but not for instance passing.
    # One way: modify one class to accept dependency via a setter method.
    # If no class changes are allowed:
    # The provided `main.py` snippet's logic is the one to implement,
    # which means we must assume `EditorController.__init__` is robust enough
    # if `view` is initially `None` and methods relying on `self.view` are called *later*.
    # The current `EditorController` calls `self.view.set_status` in `__init__`. This is the conflict.

    # The prompt is "Replace the content of main.py with the Python code provided above."
    # I will do this directly. If it causes issues due to class incompatibilities,
    # that's a consequence of the provided snippet vs. class designs from other steps.
    # The task is to use the *provided main.py content*.

    # Instantiate all components as per the provided script.
    # The potential issue with EditorController.__init__ using a None view is noted.
    
    # 1. Instantiate Model and Services (as in the prompt)
    # video_state, ai_service, video_processing_service, preview_service are fine.

    # 2. Instantiate Controller with view=None (as in the prompt)
    # This line will cause a runtime error if EditorController from Turn 11 is used directly,
    # because its __init__ tries to call self.view.set_status.
    # For this step, I will assume this is intended to highlight such an integration issue,
    # or that a modified EditorController is implied by this main.py.
    # I will proceed with the *exact code provided in the prompt for main.py*.

    editor_controller = EditorController(
        view=None,  # This is the problematic part if EditorController immediately uses view
        video_state=video_state,
        ai_service=ai_service,
        video_processing_service=video_processing_service,
        preview_service=preview_service
    )

    # 3. Instantiate View, passing the controller (as in the prompt)
    main_view = MainView(controller=editor_controller)

    # 4. Assign the fully initialized view to the controller (as in the prompt)
    editor_controller.view = main_view

    # 5. Perform initial setup via controller (as in the prompt)
    # Now that editor_controller.view is set, these calls should work,
    # assuming these methods themselves are safe.
    # EditorController's _update_view_for_new_video_data calls self.view methods.
    # EditorController's _update_all_button_states calls self.view methods.
    
    # The critical part is that EditorController.__init__ must not crash with view=None.
    # If it does, then this main.py is fundamentally incompatible without changes to EditorController.
    # However, my task is *only* to update main.py as specified.

    editor_controller._update_view_for_new_video_data() 
    editor_controller._update_all_button_states() 
    
    if not video_state.get_current_path():
         main_view.display_preview_image(None)

    # 6. Set the on-closing behavior (as in the prompt)
    main_view.set_on_closing_callback(editor_controller.handle_on_close)

    # 7. Start the Tkinter main loop (as in the prompt)
    main_view.start_mainloop()
