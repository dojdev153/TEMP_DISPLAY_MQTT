import time
import serial

SERIAL_PORT = "COM12"
BAUD_RATE = 9600


def main():
    arduino = None

    try:
        print(f"Connecting to Arduino on {SERIAL_PORT}...")

        arduino = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2,
        )

        # Arduino normally restarts when Python opens the serial port.
        time.sleep(2)
        arduino.reset_input_buffer()

        print(f"Connected successfully to {SERIAL_PORT}")
        print("Waiting for temperature values...")
        print("Press Ctrl+C to stop.\n")

        while True:
            raw_line = arduino.readline()

            if not raw_line:
                continue

            line = raw_line.decode("utf-8", errors="ignore").strip()

            if not line:
                continue

            if line.startswith("TEMP:"):
                try:
                    temperature_text = line.split(":", 1)[1]
                    temperature = float(temperature_text)

                    print(f"Temperature: {temperature:.2f} °C")

                except ValueError:
                    print(f"Invalid temperature value: {line}")
            else:
                print(f"Arduino message: {line}")

    except serial.SerialException as error:
        print(f"\nSerial connection error: {error}")
        print("Make sure:")
        print("1. Arduino is connected.")
        print("2. COM12 is correct.")
        print("3. Arduino Serial Monitor is closed.")

    except KeyboardInterrupt:
        print("\nProgram stopped by user.")

    finally:
        if arduino is not None and arduino.is_open:
            arduino.close()
            print("Serial port closed.")


if __name__ == "__main__":
    main()