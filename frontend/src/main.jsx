import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

import {
  Camera,
  FileImage,
  LayoutDashboard,
  LogOut,
  History as HistoryIcon,
  Upload,
  FileText,
  Video,
  MapPin,
  RefreshCw
} from 'lucide-react';

import {
  MapContainer,
  TileLayer,
  Marker,
  Popup
} from 'react-leaflet';

import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import api from './services/api';
import './style.css';


/* =========================================================
   API / SERVER URL HELPERS
========================================================= */

const API_URL =
  import.meta.env.VITE_API_URL ||
  'https://roadvision-ai-api.up.railway.app/api';


/*
  Converts:

  https://roadvision-ai-api.up.railway.app/api
  ->
  https://roadvision-ai-api.up.railway.app
*/

const SERVER_URL =
  API_URL.replace(/\/api\/?$/, '');


/*
  Convert backend result URLs into
  complete browser-accessible URLs.

  Handles:

  /uploads/result.jpg
  uploads/result.jpg
  /uploads/result.jpg
  uploads/result.jpg
  http://localhost:8000/uploads/result.jpg
  https://roadvision-ai-api.up.railway.app/uploads/result.jpg
*/

function getMediaUrl(url) {

  if (!url) {
    return null;
  }

  /*
    Already an absolute URL.
  */

  if (
    url.startsWith('http://') ||
    url.startsWith('https://')
  ) {

    /*
      If backend accidentally returned localhost
      while the frontend is using Render, replace
      localhost with the current configured server.
    */

    const localBackendPrefixes = [
      'http://localhost:8000',
      'http://127.0.0.1:8000',
      'http://0.0.0.0:8000'
    ];

    const localPrefix =
      localBackendPrefixes.find((prefix) =>
        url.startsWith(prefix)
      );

    if (localPrefix) {
      return SERVER_URL + url.slice(localPrefix.length);
    }

    return url;

  }


  /*
    Relative URL.
  */

  if (url.startsWith('/')) {

    return SERVER_URL + url;

  }


  return `${SERVER_URL}/${url}`;

}


/* =========================================================
   LEAFLET MARKER FIX
========================================================= */

delete L.Icon.Default.prototype._getIconUrl;

L.Icon.Default.mergeOptions({

  iconRetinaUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',

  iconUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',

  shadowUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'

});


/* =========================================================
   NAVIGATION
========================================================= */

const nav = [

  [
    'dashboard',
    LayoutDashboard,
    'Dashboard'
  ],

  [
    'image',
    FileImage,
    'Image Detection'
  ],

  [
    'video',
    Video,
    'Video Detection'
  ],

  [
    'live',
    Camera,
    'Live Camera'
  ],

  [
    'history',
    HistoryIcon,
    'History'
  ]

];


/* =========================================================
   AUTHENTICATION
========================================================= */

function Auth({ onLogin }) {

  const [register, setRegister] =
    useState(false);

  const [email, setEmail] =
    useState('');

  const [password, setPassword] =
    useState('');

  const [error, setError] =
    useState('');


  const submit = async (e) => {

    e.preventDefault();

    setError('');

    try {

      const r = await api.post(
        `/auth/${register ? 'register' : 'login'}`,
        {
          email,
          password
        }
      );


      localStorage.setItem(
        'roadvision_token',
        r.data.access_token
      );


      onLogin();

    } catch (e) {

      setError(
        e.response?.data?.detail ||
        'Unable to sign in'
      );

    }

  };


  return (

    <main className="auth">

      <section>

        <p className="eyebrow">
          ROADVISION AI
        </p>

        <h1>
          Infrastructure intelligence,
          <br />
          <i>made visible.</i>
        </h1>

        <p>
          Inspect road imagery, assess risk,
          and create evidence-based maintenance reports.
        </p>

      </section>


      <form onSubmit={submit}>

        <h2>
          {register
            ? 'Create account'
            : 'Welcome back'}
        </h2>

        <p>
          {register
            ? 'Start your inspection workspace.'
            : 'Sign in to your workspace.'}
        </p>


        <input
          placeholder="Work email"
          type="email"
          value={email}
          onChange={(e) =>
            setEmail(e.target.value)
          }
          required
        />


        <input
          placeholder="Password (8+ characters)"
          type="password"
          value={password}
          onChange={(e) =>
            setPassword(e.target.value)
          }
          required
          minLength="8"
        />


        {error && (

          <small>
            {error}
          </small>

        )}


        <button type="submit">

          {register
            ? 'Create account'
            : 'Sign in'}

        </button>


        <a
          onClick={() =>
            setRegister(!register)
          }
        >

          {register
            ? 'Already have an account? Sign in'
            : 'New here? Create an account'}

        </a>

      </form>

    </main>

  );

}


/* =========================================================
   GET CURRENT GPS LOCATION
========================================================= */

function getCurrentLocation() {

  return new Promise(
    (resolve, reject) => {

      if (!navigator.geolocation) {

        reject(
          new Error(
            'GPS is not supported by this browser.'
          )
        );

        return;

      }


      navigator.geolocation.getCurrentPosition(

        (position) => {

          resolve({

            latitude:
              position.coords.latitude,

            longitude:
              position.coords.longitude,

            accuracy:
              position.coords.accuracy

          });

        },

        (error) => {

          reject(error);

        },

        {

          enableHighAccuracy: true,

          timeout: 15000,

          maximumAge: 0

        }

      );

    }
  );

}


/* =========================================================
   IMAGE DETECTION + GPS
========================================================= */

function UploadPage({ onResult }) {

  const [file, setFile] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [locationLoading, setLocationLoading] =
    useState(false);

  const [message, setMessage] =
    useState('');

  const [location, setLocation] =
    useState(null);


  const getLocation = async () => {

    setLocationLoading(true);

    setMessage('');

    try {

      const loc =
        await getCurrentLocation();

      setLocation(loc);

      setMessage(
        '📍 Location captured successfully.'
      );

    } catch (error) {

      if (error.code === 1) {

        setMessage(
          '📍 Location permission denied. You can still continue without GPS.'
        );

      } else if (error.code === 2) {

        setMessage(
          '📍 Unable to determine location. You can still continue without GPS.'
        );

      } else if (error.code === 3) {

        setMessage(
          '📍 Location request timed out. You can still continue without GPS.'
        );

      } else {

        setMessage(
          '📍 GPS unavailable. You can still continue without GPS.'
        );

      }

    } finally {

      setLocationLoading(false);

    }

  };


  const send = async () => {

    if (!file) {

      setMessage(
        'Please select an image first.'
      );

      return;

    }


    setLoading(true);

    setMessage('');


    try {

      let currentLocation =
        location;


      if (!currentLocation) {

        setMessage(
          '📍 Trying to get your location...'
        );

        try {

          currentLocation =
            await getCurrentLocation();

          setLocation(
            currentLocation
          );

        } catch {

          currentLocation =
            null;

        }

      }


      const data =
        new FormData();


      data.append(
        'file',
        file
      );


      if (currentLocation) {

        data.append(
          'latitude',
          String(
            currentLocation.latitude
          )
        );

        data.append(
          'longitude',
          String(
            currentLocation.longitude
          )
        );

      }


      setMessage(
        '🤖 Analyzing road image...'
      );


      const r =
        await api.post(
          '/detection/image',
          data
        );


      const result = {

        ...r.data,

        latitude:
          r.data.latitude ??
          currentLocation?.latitude ??
          null,

        longitude:
          r.data.longitude ??
          currentLocation?.longitude ??
          null,

        location_accuracy:
          r.data.location_accuracy ??
          currentLocation?.accuracy ??
          null

      };


      onResult(result);

    } catch (error) {

      setMessage(

        error.response?.data?.detail ||

        error.message ||

        'Upload failed. Is the backend available?'

      );

    } finally {

      setLoading(false);

    }

  };


  return (

    <Page
      title="Image Detection"
      sub="Upload road imagery for an on-demand visual inspection."
    >

      <div className="upload">

        <Upload size={34} />

        <h3>
          Drop a road image here
        </h3>

        <p>
          JPG, PNG, or WEBP · up to 100 MB
        </p>


        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(e) => {

            setFile(
              e.target.files?.[0] ||
              null
            );

            setMessage('');

          }}
        />


        {file && (

          <b>
            {file.name}
          </b>

        )}


        <div className="location-box">

          <div className="location-status">

            <span className="location-dot"></span>

            <strong>
              📍 GPS Location
            </strong>

          </div>


          {!location ? (

            <>

              <p>
                Capture your current location
                and associate it with this road
                inspection.
              </p>


              <button
                type="button"
                className="location-button"
                onClick={getLocation}
                disabled={
                  locationLoading ||
                  loading
                }
              >

                {locationLoading
                  ? 'Getting location...'
                  : '📍 Get Current Location'}

              </button>

            </>

          ) : (

            <>

              <p>
                ✅ Location captured successfully.
              </p>


              <div className="coordinates">

                <div>
                  Latitude:{' '}
                  {location.latitude.toFixed(6)}
                </div>

                <div>
                  Longitude:{' '}
                  {location.longitude.toFixed(6)}
                </div>

                {location.accuracy != null && (

                  <div>
                    Accuracy: ±
                    {Math.round(
                      location.accuracy
                    )}{' '}
                    m
                  </div>

                )}

              </div>


              <button
                type="button"
                className="location-button"
                onClick={getLocation}
                disabled={
                  locationLoading ||
                  loading
                }
              >

                <RefreshCw size={15} />

                {locationLoading
                  ? 'Updating...'
                  : 'Refresh Location'}

              </button>

            </>

          )}

        </div>


        <button
          type="button"
          onClick={send}
          disabled={
            !file ||
            loading
          }
        >

          {loading
            ? 'Analyzing...'
            : 'Run AI inspection'}

        </button>


        {message && (

          <p>
            {message}
          </p>

        )}

      </div>

    </Page>

  );

}


/* =========================================================
   VIDEO DETECTION
========================================================= */

function VideoPage({ onResult }) {

  const [file, setFile] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [message, setMessage] =
    useState('');


  const send = async () => {

    if (!file) {

      setMessage(
        'Please select a video first.'
      );

      return;

    }


    setLoading(true);

    setMessage('');


    try {

      const form =
        new FormData();


      form.append(
        'file',
        file
      );


      const r =
        await api.post(
          '/detection/video',
          form
        );


      onResult(r.data);

    } catch (e) {

      setMessage(
        e.response?.data?.detail ||
        'Video processing failed.'
      );

    } finally {

      setLoading(false);

    }

  };


  return (

    <Page
      title="Video Detection"
      sub="Process video with configurable frame skipping for practical performance."
    >

      <div className="upload">

        <Video size={34} />

        <h3>
          Upload a road video
        </h3>

        <p>
          MP4, AVI, MOV, or MKV · up to 100 MB
        </p>


        <input
          type="file"
          accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska"
          onChange={(e) =>
            setFile(
              e.target.files?.[0] ||
              null
            )
          }
        />


        {file && (

          <b>
            {file.name}
          </b>

        )}


        <button
          type="button"
          onClick={send}
          disabled={
            !file ||
            loading
          }
        >

          {loading
            ? 'Processing frames...'
            : 'Analyze video'}

        </button>


        {message && (

          <p>
            {message}
          </p>

        )}

      </div>

    </Page>

  );

}


/* =========================================================
   DASHBOARD
========================================================= */

function Dashboard() {

  const [stats, setStats] =
    useState(null);


  useEffect(() => {

    api
      .get('/dashboard/statistics')

      .then((r) => {

        setStats(r.data);

      })

      .catch(() => {});

  }, []);


  const d =
    stats || {

      total_inspections: 0,

      total_damages: 0,

      potholes: 0,

      cracks: 0,

      high_severity: 0,

      average_confidence: 0,

      types: {}

    };


  const cards = [

    [
      'Total inspections',
      d.total_inspections
    ],

    [
      'Detected damage',
      d.total_damages
    ],

    [
      'Potholes',
      d.potholes
    ],

    [
      'High severity',
      d.high_severity
    ],

    [
      'Average confidence',
      `${Math.round(
        d.average_confidence * 100
      )}%`
    ]

  ];


  return (

    <Page
      title="Inspection overview"
      sub="A live summary of your road-condition intelligence."
    >

      <div className="cards">

        {cards.map(
          ([label, value]) => (

            <article key={label}>

              <span>
                {label}
              </span>

              <strong>
                {value}
              </strong>

            </article>

          )
        )}

      </div>


      <section className="chart">

        <h3>
          Damage type distribution
        </h3>


        <ResponsiveContainer
          width="100%"
          height={280}
        >

          <BarChart
            data={
              Object.entries(
                d.types
              ).map(
                ([name, value]) => ({
                  name,
                  value
                })
              )
            }
          >

            <XAxis
              dataKey="name"
            />

            <YAxis />

            <Tooltip />

            <Bar
              dataKey="value"
              fill="#36c6a3"
              radius={[
                6,
                6,
                0,
                0
              ]}
            />

          </BarChart>

        </ResponsiveContainer>

      </section>

    </Page>

  );

}


/* =========================================================
   REVERSE GEOCODING
========================================================= */

async function reverseGeocode(
  latitude,
  longitude,
  signal
) {

  try {

    const url =
      `https://nominatim.openstreetmap.org/reverse` +
      `?format=jsonv2` +
      `&lat=${encodeURIComponent(latitude)}` +
      `&lon=${encodeURIComponent(longitude)}` +
      `&zoom=18` +
      `&addressdetails=1`;


    const response =
      await fetch(
        url,
        {
          method: 'GET',

          headers: {
            Accept:
              'application/json'
          },

          signal
        }
      );


    if (!response.ok) {

      throw new Error(
        'Reverse geocoding request failed'
      );

    }


    const data =
      await response.json();


    const address =
      data.address || {};


    const city =
      address.city ||
      address.town ||
      address.municipality ||
      address.village ||
      address.suburb ||
      address.county ||
      '';


    const state =
      address.state ||
      address.state_district ||
      '';


    const country =
      address.country ||
      '';


    const postcode =
      address.postcode ||
      '';


    const mainParts =
      [
        city,
        state,
        country
      ].filter(Boolean);


    let shortName =
      mainParts.join(', ');


    if (
      !shortName &&
      data.display_name
    ) {

      shortName =
        data.display_name;

    }


    const detailedParts =
      [
        address.road,
        city,
        state,
        postcode,
        country
      ].filter(Boolean);


    const detailedName =
      detailedParts.join(', ');


    return {

      name:
        shortName ||
        'Location name unavailable',

      detailedName:
        detailedName ||
        data.display_name ||
        'Location details unavailable',

      city,

      state,

      country,

      postcode

    };

  } catch (error) {

    if (
      error.name ===
      'AbortError'
    ) {

      throw error;

    }


    return {

      name:
        'Location name unavailable',

      detailedName:
        'Unable to determine place name',

      city: '',

      state: '',

      country: '',

      postcode: ''

    };

  }

}


/* =========================================================
   GPS MAP + PLACE NAME
========================================================= */

function InspectionMap({
  latitude,
  longitude
}) {

  const lat =
    Number(latitude);

  const lng =
    Number(longitude);


  const [
    place,
    setPlace
  ] = useState(null);


  const [
    placeLoading,
    setPlaceLoading
  ] = useState(true);


  useEffect(() => {

    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lng)
    ) {

      setPlaceLoading(false);

      return;

    }


    const controller =
      new AbortController();


    const findPlace =
      async () => {

        setPlaceLoading(true);

        const result =
          await reverseGeocode(
            lat,
            lng,
            controller.signal
          );


        if (
          !controller.signal.aborted
        ) {

          setPlace(result);

          setPlaceLoading(false);

        }

      };


    findPlace();


    return () => {

      controller.abort();

    };

  }, [lat, lng]);


  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng)
  ) {

    return null;

  }


  return (

    <div className="gps-map-wrapper">


      <div className="place-name">

        <div className="place-icon">

          <MapPin size={20} />

        </div>


        <div className="place-info">

          <span className="place-label">
            INSPECTION LOCATION
          </span>


          {placeLoading ? (

            <strong>
              Finding location...
            </strong>

          ) : (

            <strong>
              {place?.name ||
                'Location name unavailable'}
            </strong>

          )}


          {!placeLoading &&
            place?.detailedName &&
            place.detailedName !==
              place.name && (

              <small>
                {place.detailedName}
              </small>

            )}

        </div>

      </div>


      <div className="gps-map">

        <MapContainer
          center={[
            lat,
            lng
          ]}
          zoom={16}
          scrollWheelZoom={true}
          style={{
            height: '320px',
            width: '100%'
          }}
        >

          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />


          <Marker
            position={[
              lat,
              lng
            ]}
          >

            <Popup>

              <strong>
                RoadVision AI
              </strong>

              <br />

              {place?.name ||
                'Inspection Location'}

              <br />

              <br />

              <strong>
                Coordinates
              </strong>

              <br />

              {lat.toFixed(6)}
              {', '}
              {lng.toFixed(6)}

            </Popup>

          </Marker>

        </MapContainer>

      </div>

    </div>

  );

}


/* =========================================================
   RESULT PAGE
========================================================= */

function Result({ data }) {

  if (!data) {

    return (

      <Page
        title="Inspection result"
        sub="Run an image inspection to see annotated results."
      >

        <div className="empty">
          No inspection selected.
        </div>

      </Page>

    );

  }


  /*
    IMPORTANT:

    Do NOT use:

    http://localhost:8000${data.result_url}

    here.

    The deployed frontend must use the Railway
    backend URL.
  */

  const media =
    getMediaUrl(
      data.result_url
    );


  const report =
    getMediaUrl(
      data.report_url
    );


  const hasLocation =
    data.latitude !== undefined &&
    data.latitude !== null &&
    data.longitude !== undefined &&
    data.longitude !== null;


  const googleMapsUrl =
    hasLocation
      ? `https://www.google.com/maps?q=${data.latitude},${data.longitude}`
      : null;


  return (

    <Page
      title={`Inspection #${data.id}`}
      sub={
        data.demo_notice ||
        `${data.total_detections ?? 0} detections recorded`
      }
    >

      <div className="result">


        {/* =================================================
            IMAGE / VIDEO
        ================================================= */}

        {media ? (

          data.input_type === 'video' ? (

            <video
              controls
              src={media}
            />

          ) : (

            <img
              src={media}
              alt="Road inspection result"
              onError={(e) => {

                console.error(
                  'Unable to load result media:',
                  media
                );

                e.currentTarget.style.display =
                  'none';

              }}
            />

          )

        ) : (

          <div className="empty">

            Result media is not available.

          </div>

        )}


        <section>

          <h3>
            Detection summary
          </h3>


          <div className="cards small">

            <article>

              <span>
                Total
              </span>

              <strong>
                {data.total_detections ?? 0}
              </strong>

            </article>


            <article>

              <span>
                Highest severity
              </span>

              <strong>
                {data.highest_severity || 'None'}
              </strong>

            </article>

          </div>


          {/* =================================================
              GPS
          ================================================= */}

          {hasLocation ? (

            <div className="gps-result">

              <h4>

                <MapPin
                  size={18}
                />

                {' '}Inspection Location

              </h4>


              <p>
                GPS coordinates captured
                with this inspection.
              </p>


              <div className="coordinates">

                <div>
                  Latitude:{' '}
                  {Number(
                    data.latitude
                  ).toFixed(6)}
                </div>


                <div>
                  Longitude:{' '}
                  {Number(
                    data.longitude
                  ).toFixed(6)}
                </div>


                {data.location_accuracy != null && (

                  <div>
                    Accuracy: ±
                    {Math.round(
                      data.location_accuracy
                    )}{' '}
                    m
                  </div>

                )}

              </div>


              <InspectionMap
                latitude={
                  data.latitude
                }
                longitude={
                  data.longitude
                }
              />


              <a
                className="button"
                href={googleMapsUrl}
                target="_blank"
                rel="noopener noreferrer"
              >

                🗺️ Open in Google Maps

              </a>

            </div>

          ) : (

            <div className="gps-result">

              <h4>

                <MapPin
                  size={18}
                />

                {' '}Inspection Location

              </h4>


              <p>
                No GPS location was recorded
                for this inspection.
              </p>

            </div>

          )}


          {/* =================================================
              DETECTIONS
          ================================================= */}

          {data.detections &&
          data.detections.length > 0 ? (

            data.detections.map(
              (x, i) => (

                <div
                  className="detection"
                  key={i}
                >

                  <b>
                    {String(
                      x.class_name ||
                      'Unknown'
                    ).replaceAll(
                      '_',
                      ' '
                    )}
                  </b>


                  <span>

                    {Math.round(
                      Number(
                        x.confidence || 0
                      ) * 100
                    )}

                    % · {x.severity || 'Unknown'} ·{' '}

                    {Number(
                      x.area_pixels || 0
                    ).toLocaleString()}

                    {' '}px²

                  </span>

                </div>

              )
            )

          ) : (

            <p>
              No detections were produced.
              Install calibrated custom YOLO
              weights for real road-damage inference.
            </p>

          )}


          {/* =================================================
              PDF REPORT
          ================================================= */}

          {report && (

            <a
              className="button"
              href={report}
              target="_blank"
              rel="noopener noreferrer"
            >

              📄 Download PDF report

            </a>

          )}

        </section>

      </div>

    </Page>

  );

}


/* =========================================================
   LIVE CAMERA
========================================================= */

function Live({ onResult }) {

  const ref =
    useRef(null);

  const [on, setOn] =
    useState(false);

  const [msg, setMsg] =
    useState('');


  const start = async () => {

    try {

      const stream =
        await navigator.mediaDevices.getUserMedia(
          {
            video: {
              facingMode: {
                ideal: 'environment'
              }
            },

            audio: false
          }
        );


      if (ref.current) {

        ref.current.srcObject =
          stream;

      }


      setOn(true);

      setMsg('');

    } catch {

      setMsg(
        'Camera permission was denied or no camera is available.'
      );

    }

  };


  const capture = async () => {

    if (!ref.current) {

      return;

    }


    if (
      !ref.current.videoWidth ||
      !ref.current.videoHeight
    ) {

      setMsg(
        'Camera is not ready yet.'
      );

      return;

    }


    const canvas =
      document.createElement(
        'canvas'
      );


    canvas.width =
      ref.current.videoWidth;


    canvas.height =
      ref.current.videoHeight;


    const context =
      canvas.getContext('2d');


    context.drawImage(
      ref.current,
      0,
      0
    );


    const blob =
      await new Promise(
        (resolve) => {

          canvas.toBlob(
            resolve,
            'image/jpeg',
            0.92
          );

        }
      );


    if (!blob) {

      setMsg(
        'Unable to capture camera frame.'
      );

      return;

    }


    const form =
      new FormData();


    form.append(
      'file',
      blob,
      'camera.jpg'
    );


    try {

      const r =
        await api.post(
          '/detection/live',
          form
        );


      onResult(r.data);

    } catch (error) {

      setMsg(
        error.response?.data?.detail ||
        'Unable to analyze camera frame.'
      );

    }

  };


  const stopCamera = () => {

    const stream =
      ref.current?.srcObject;


    if (stream) {

      stream
        .getTracks()
        .forEach(
          (track) =>
            track.stop()
        );

    }


    if (ref.current) {

      ref.current.srcObject =
        null;

    }


    setOn(false);

  };


  return (

    <Page
      title="Live camera"
      sub="Capture a frame from your browser camera for backend inference."
    >

      <div className="camera">

        <video
          ref={ref}
          autoPlay
          playsInline
          muted
        />


        {!on ? (

          <button
            type="button"
            onClick={start}
          >

            Enable camera

          </button>

        ) : (

          <>

            <button
              type="button"
              onClick={capture}
            >

              Analyze current frame

            </button>


            <button
              type="button"
              className="location-button"
              onClick={stopCamera}
            >

              Stop camera

            </button>

          </>

        )}


        {msg && (

          <p>
            {msg}
          </p>

        )}

      </div>

    </Page>

  );

}


/* =========================================================
   HISTORY
========================================================= */

function History({ setResult }) {

  const [items, setItems] =
    useState([]);

  const [loading, setLoading] =
    useState(true);


  useEffect(() => {

    api
      .get('/inspections')

      .then((r) => {

        setItems(
          Array.isArray(r.data)
            ? r.data
            : []
        );

      })

      .catch(() => {

        setItems([]);

      })

      .finally(() => {

        setLoading(false);

      });

  }, []);


  return (

    <Page
      title="Inspection history"
      sub="Your saved image and camera inspections."
    >

      <div className="table">

        {loading ? (

          <div className="empty">
            Loading inspection history...
          </div>

        ) : items.length > 0 ? (

          items.map((i) => (

            <button
              type="button"
              className="row"
              onClick={() =>
                setResult(i)
              }
              key={i.id}
            >

              <b>
                #{i.id} · {i.filename}
              </b>


              <span>
                {new Date(
                  i.created_at
                ).toLocaleString()}
              </span>


              <span>
                {i.total_detections}
                {' '}detections
              </span>


              <em>
                {i.highest_severity}
              </em>

            </button>

          ))

        ) : (

          <div className="empty">
            No saved inspections yet.
          </div>

        )}

      </div>

    </Page>

  );

}


/* =========================================================
   COMMON PAGE
========================================================= */

function Page({
  title,
  sub,
  children
}) {

  return (

    <main className="page">

      <header>

        <p className="eyebrow">
          OPERATIONS / ROAD INSPECTION
        </p>

        <h1>
          {title}
        </h1>

        <p>
          {sub}
        </p>

      </header>

      {children}

    </main>

  );

}


/* =========================================================
   MAIN APP
========================================================= */

function App() {

  const [authed, setAuthed] =
    useState(
      !!localStorage.getItem(
        'roadvision_token'
      )
    );


  const [page, setPage] =
    useState('dashboard');


  const [result, setResult] =
    useState(null);


  const showResult = (data) => {

    setResult(data);

    setPage('result');

  };


  if (!authed) {

    return (

      <Auth
        onLogin={() =>
          setAuthed(true)
        }
      />

    );

  }


  let content;


  if (page === 'dashboard') {

    content =
      <Dashboard />;

  }

  else if (page === 'image') {

    content = (

      <UploadPage
        onResult={showResult}
      />

    );

  }

  else if (page === 'video') {

    content = (

      <VideoPage
        onResult={showResult}
      />

    );

  }

  else if (page === 'live') {

    content = (

      <Live
        onResult={showResult}
      />

    );

  }

  else if (page === 'history') {

    content = (

      <History
        setResult={showResult}
      />

    );

  }

  else {

    content = (

      <Result
        data={result}
      />

    );

  }


  return (

    <div className="shell">

      <aside>

        <div className="brand">

          <span>
            ◒
          </span>

          {' '}RoadVision{' '}

          <b>
            AI
          </b>

        </div>


        <nav>

          {nav.map(
            ([id, Icon, label]) => (

              <button
                type="button"
                className={
                  page === id
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  setPage(id)
                }
                key={id}
              >

                <Icon size={18} />

                {label}

              </button>

            )
          )}


          <button
            type="button"
            className={
              page === 'result'
                ? 'active'
                : ''
            }
            onClick={() =>
              setPage('result')
            }
          >

            <FileText size={18} />

            Results

          </button>

        </nav>


        <button
          type="button"
          className="logout"
          onClick={() => {

            localStorage.removeItem(
              'roadvision_token'
            );

            setAuthed(false);

            setPage(
              'dashboard'
            );

            setResult(null);

          }}
        >

          <LogOut size={18} />

          Logout

        </button>

      </aside>


      {content}

    </div>

  );

}


/* =========================================================
   START APPLICATION
========================================================= */

createRoot(
  document.getElementById('root')
).render(
  <App />
);
