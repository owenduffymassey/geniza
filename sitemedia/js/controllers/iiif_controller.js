// controllers/iiif_controller.js

import { Controller } from "@hotwired/stimulus";
import OpenSeadragon from "openseadragon";

export default class extends Controller {
    static targets = [
        "imageHeader",
        "osd",
        "rotateLeft",
        "rotateRight",
        "image",
        "zoomSlider",
        "zoomSliderLabel",
        "zoomToggle",
    ];

    osdTargetDisconnected() {
        // remove OSD on target disconnect (i.e. leaving page)
        this.deactivateDeepZoom();
    }
    handleDeepZoom(evt) {
        // Enable OSD and/or zoom based on zoom slider level
        // OSD needs to use DOM queries since it can't be assigned a target
        const OSD = this.osdTarget.querySelector(".openseadragon-container");
        if (!OSD || this.osdTarget.classList.contains("hidden")) {
            const isMobile = evt.currentTarget.id.startsWith("zoom-toggle");
            this.activateDeepZoom({ isMobile });
        }
    }
    activateDeepZoom(settings) {
        // scroll to top of controls
        this.imageHeaderTarget.scrollIntoView();
        // hide image and add OpenSeaDragon to container
        let OSD = this.osdTarget.querySelector(".openseadragon-container");
        if (!OSD) {
            this.addOpenSeaDragon(settings);
        }
        this.imageTarget.classList.remove("visible");
        this.imageTarget.classList.add("hidden");
        this.osdTarget.classList.remove("hidden");
        this.osdTarget.classList.add("visible");
        this.rotateRightTarget.removeAttribute("disabled");
        this.rotateLeftTarget.removeAttribute("disabled");
    }
    deactivateDeepZoom() {
        this.imageTarget.classList.add("visible");
        this.imageTarget.classList.remove("hidden");
        this.osdTarget.classList.remove("visible");
        this.osdTarget.classList.add("hidden");
        this.rotateRightTarget.setAttribute("disabled", "true");
        this.rotateLeftTarget.setAttribute("disabled", "true");
    }
    addOpenSeaDragon(settings) {
        const { isMobile } = settings;

        // constants for OSD
        const minZoom = 1.0; // Minimum zoom as a multiple of image size
        const maxZoom = 1.5; // Maximum zoom as a multiple of image size

        // inject OSD into the image container
        let viewer = OpenSeadragon({
            element: this.osdTarget,
            prefixUrl:
                "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/3.0.0/images/",
            tileSources: [this.osdTarget.dataset.iiifUrl],
            sequenceMode: false,
            autoHideControls: true,
            showHomeControl: false,
            showZoomControl: false,
            showNavigationControl: false,
            showFullPageControl: false,
            showSequenceControl: false,
            crossOriginPolicy: "Anonymous",
            gestureSettingsTouch: {
                pinchRotate: true,
            },
            minZoomImageRatio: minZoom,
            maxZoomPixelRatio: maxZoom,
        });
        viewer.addHandler("open", () => {
            // zoom to current zoom
            viewer.viewport.zoomTo(parseFloat(this.zoomSliderTarget.value));
            // ensure image is positioned in top-left corner of viewer
            this.resetBounds(viewer);
            if (isMobile) {
                // zoom to 110% if on mobile
                viewer.viewport.zoomTo(1.1);
                if (!this.zoomToggleTarget.checked) {
                    this.zoomToggleTarget.checked = true;
                }
            }
            // initialize zoom slider
            this.zoomSliderTarget.setAttribute("min", minZoom);
            // use toPrecision to ensure no extra pixels on the right of the slider
            this.zoomSliderTarget.setAttribute(
                "max",
                viewer.viewport.getMaxZoom().toPrecision(2)
            );
            this.zoomSliderTarget.addEventListener(
                "input",
                this.handleZoomSliderInput(viewer, minZoom)
            );
            // initialize mobile zoom toggle
            this.zoomToggleTarget.addEventListener("input", (evt) => {
                // always first zoom to 100%
                viewer.viewport.zoomTo(1.0);
                if (!evt.currentTarget.checked) {
                    // wait to reset bounds until element is hidden
                    setTimeout(() => this.resetBounds(viewer), 300);
                    this.deactivateDeepZoom();
                } else {
                    // reset bounds immediately and zoom to 110%
                    this.resetBounds(viewer);
                    viewer.viewport.zoomTo(1.1);
                }
            });
            // initialize desktop rotation buttons
            this.rotateLeftTarget.addEventListener("click", () => {
                viewer.viewport.setRotation(viewer.viewport.getRotation() - 90);
            });
            this.rotateRightTarget.addEventListener("click", () => {
                viewer.viewport.setRotation(viewer.viewport.getRotation() + 90);
            });
        });
        viewer.addHandler("zoom", (evt) => {
            // Handle changes in the canvas zoom
            let { zoom } = evt;
            if (zoom <= minZoom) {
                // If zooming to less than 100%, force it to 100%
                zoom = minZoom;
            }
            // Set zoom slider value to the chosen percentage
            this.zoomSliderTarget.value = parseFloat(zoom);
            this.updateZoomUI(zoom, false);
        });
    }
    handleZoomSliderInput(viewer, minZoom) {
        return (evt) => {
            // Handle changes in the zoom slider
            let zoom = parseFloat(evt.currentTarget.value);
            let deactivating = false;
            if (zoom <= minZoom) {
                // When zoomed back out to 100%, deactivate OSD
                zoom = minZoom;
                viewer.viewport.zoomTo(1.0);
                this.resetBounds(viewer);
                this.deactivateDeepZoom();
                deactivating = true;
                evt.currentTarget.value = minZoom;
            } else {
                // Zoom to the chosen percentage
                viewer.viewport.zoomTo(zoom);
            }
            this.updateZoomUI(zoom, deactivating);
        };
    }
    updateZoomUI(zoom, deactivating) {
        // update the zoom controls UI with the new value

        // update the zoom percentage label
        this.zoomSliderLabelTarget.textContent = `${(zoom * 100).toFixed(0)}%`;
        // update progress indication in slider track
        const percent =
            (zoom / this.zoomSliderTarget.getAttribute("max")) * 100;
        let secondColor = "var(--filter-active)";
        if (deactivating) {
            secondColor = "#9E9E9E";
            this.zoomSliderTarget.classList.remove("active-thumb");
        } else if (!this.zoomSliderTarget.classList.contains("active-thumb")) {
            this.zoomSliderTarget.classList.add("active-thumb");
        }
        this.zoomSliderTarget.style.background = `linear-gradient(to right, var(--link-primary) 0%, var(--link-primary) ${percent}%, ${secondColor} ${percent}%, ${secondColor} 100%)`;
    }
    resetBounds(viewer) {
        // Reset OSD viewer to the boundaries of the image, position in top left corner
        // (cannot use viewport.goHome() without hacks, as its bounds cannot be configured)
        const bounds = viewer.viewport.getBounds();
        const newBounds = new OpenSeadragon.Rect(
            0,
            0,
            bounds.width,
            bounds.height
        );
        viewer.viewport.fitBounds(newBounds, true);
        viewer.viewport.setRotation(0, true);
    }
}
