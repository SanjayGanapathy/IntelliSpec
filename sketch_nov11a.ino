const int ledPin = 13;      // Pin connected to the LED
const int sensorPin = A0;   // Sensor (photodiode) connected to analog pin A0
float iVoltage = 0;     // Voltage reading with the blank (no sample)
float darkVoltage = 0.02;      // Voltage reading in complete darkness
float voltage = 0;    // Voltage reading with the sample
float absorbance = 0;       // Calculated absorbance
float enters = 0;
float passes = 0;

void setup() {
  pinMode(ledPin, OUTPUT);    // Set the LED pin as output
  digitalWrite(ledPin, HIGH); // Turn the LED on

  Serial.begin(9600);         // Start serial communication
  Serial.println("Spectrophotometer Ready");
  Serial.println("Type 'calibrate' to calibrate with a blank or 'read' to measure a sample.");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n'); // Read user command
    command.trim(); // Remove any extra whitespace

    if (command == "calibrate") {
      calibrate();
    } else if (command == "read") {
      readSample();
    } else {
      Serial.println("Invalid command. Type 'calibrate' to calibrate or 'read' to measure a sample.");
    }
  }
}

void calibrate() {
  Serial.println("Calibrating dark signal...");
  Serial.print("Dark Voltage: ");
  Serial.println(darkVoltage);

  Serial.println("Please calibrate with blank. Waiting for 10 seconds...");
  delay(10000); // Wait for user to place the blank

  iVoltage = analogRead(sensorPin) * 5.0 / 1023.0; // Read the blank voltage
  Serial.print("Initial Voltage (Blank): ");
  Serial.println(iVoltage);

  Serial.println("Calibration complete. You can now type 'read' to measure samples.");
}

void readSample() {
  Serial.println("Place the sample. Reading in 5 seconds...");
  delay(5000); // Wait for user to place the sample

  voltage = analogRead(sensorPin) * 5.0 / 1023.0; // Read the sample voltage
  Serial.print("Voltage: ");
  Serial.println(voltage);

  // Calculate absorbance using the Beer-Lambert equation
  enters = iVoltage - darkVoltage;
  passes = voltage - darkVoltage;

   if ((enters/passes)>100) {
    absorbance=2.00;
  } else {
    absorbance = log10(enters / passes);
  }
  

  Serial.print("Absorbance: ");
  Serial.println(absorbance);
}
